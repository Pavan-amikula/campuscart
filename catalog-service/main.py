import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://campuscart:campuscart@localhost:5432/campuscart",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(300))
    total_units: Mapped[int] = mapped_column(Integer)


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    category: str = Field(min_length=2, max_length=50)
    description: str = Field(min_length=2, max_length=300)
    total_units: int = Field(ge=1, le=1000)


class EquipmentResponse(EquipmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


def get_database():
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)

    with SessionLocal() as database:
        existing_item = database.scalar(select(Equipment).limit(1))
        if existing_item is None:
            database.add_all(
                [
                    Equipment(
                        name="Canon EOS Camera",
                        category="Camera",
                        description="Digital camera for photography projects",
                        total_units=4,
                    ),
                    Equipment(
                        name="Dell Latitude Laptop",
                        category="Computer",
                        description="Laptop for student project work",
                        total_units=8,
                    ),
                    Equipment(
                        name="Epson Projector",
                        category="Presentation",
                        description="Portable classroom projector",
                        total_units=3,
                    ),
                ]
            )
            database.commit()

    yield


app = FastAPI(
    title="CampusCart Catalog API",
    description="Manages equipment available for reservation.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "catalog"}


@app.get("/equipment", response_model=list[EquipmentResponse])
def list_equipment(database: Session = Depends(get_database)):
    return database.scalars(select(Equipment).order_by(Equipment.id)).all()


@app.get("/equipment/{equipment_id}", response_model=EquipmentResponse)
def get_equipment(
    equipment_id: int,
    database: Session = Depends(get_database),
):
    equipment = database.get(Equipment, equipment_id)

    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    return equipment


@app.post(
    "/equipment",
    response_model=EquipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_equipment(
    request: EquipmentCreate,
    database: Session = Depends(get_database),
):
    equipment = Equipment(**request.model_dump())
    database.add(equipment)
    database.commit()
    database.refresh(equipment)
    return equipment