import os
from contextlib import asynccontextmanager
from datetime import date, datetime

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, DateTime, Integer, String, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://campuscart:campuscart@localhost:5432/campuscart",
)
CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog-api:8000")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(Integer, index=True)
    student_name: Mapped[str] = mapped_column(String(100))
    student_email: Mapped[str] = mapped_column(String(150))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ReservationCreate(BaseModel):
    equipment_id: int = Field(gt=0)
    student_name: str = Field(min_length=2, max_length=100)
    student_email: str = Field(min_length=5, max_length=150)
    start_date: date
    end_date: date
    quantity: int = Field(ge=1, le=100)


class ReservationResponse(ReservationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


def get_database():
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="CampusCart Reservation API",
    description="Creates equipment reservations after checking the Catalog API.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "reservation"}


@app.get("/reservations", response_model=list[ReservationResponse])
def list_reservations(database: Session = Depends(get_database)):
    query = select(Reservation).order_by(Reservation.id.desc())
    return database.scalars(query).all()


@app.get("/reservations/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: int,
    database: Session = Depends(get_database),
):
    reservation = database.get(Reservation, reservation_id)

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )

    return reservation


@app.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(
    request: ReservationCreate,
    database: Session = Depends(get_database),
):
    if request.end_date < request.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="End date must be on or after start date",
        )

    try:
        response = httpx.get(
            f"{CATALOG_URL}/equipment/{request.equipment_id}",
            timeout=5,
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Catalog service is unavailable",
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Catalog service returned an error",
        )

    equipment = response.json()

    # Serializes reservations for the same equipment to prevent overbooking.
    database.execute(
        text("SELECT pg_advisory_xact_lock(:equipment_id)"),
        {"equipment_id": request.equipment_id},
    )

    reserved_quantity = database.scalar(
        select(func.coalesce(func.sum(Reservation.quantity), 0)).where(
            Reservation.equipment_id == request.equipment_id,
            Reservation.start_date <= request.end_date,
            Reservation.end_date >= request.start_date,
        )
    )

    available_quantity = equipment["total_units"] - reserved_quantity

    if request.quantity > available_quantity:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {available_quantity} unit(s) available for these dates",
        )

    reservation = Reservation(**request.model_dump())
    database.add(reservation)
    database.commit()
    database.refresh(reservation)
    return reservation