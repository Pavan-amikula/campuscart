# CampusCart

CampusCart is a microservice application that allows university students to view and reserve shared equipment such as cameras, laptops, and projectors.

The project demonstrates REST communication, containerization, Kubernetes deployment, independent horizontal scaling, external browser access, and persistent database storage.

## Architecture

```mermaid
flowchart LR
    User[Web browser] --> Frontend[Frontend and API gateway]
    Frontend --> Catalog[Catalog REST API]
    Frontend --> Reservation[Reservation REST API]
    Reservation -->|Validates equipment through REST| Catalog
    Catalog --> PostgreSQL[(PostgreSQL)]
    Reservation --> PostgreSQL
    PostgreSQL --> PVC[(Persistent Volume)]
```

### Components

| Component | Responsibility | Kubernetes replicas |
|---|---|---:|
| Frontend | Presents the browser interface and routes API requests | 2 |
| Catalog API | Manages equipment information | 2 |
| Reservation API | Creates reservations and calls the Catalog API | 2 |
| PostgreSQL | Stores equipment and reservations | 1 |
| PersistentVolumeClaim | Preserves PostgreSQL data across Pod replacements | Not applicable |

The Catalog and Reservation APIs are separate Kubernetes Deployments, so they can be scaled independently.

## REST APIs

### Catalog API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/equipment` | List equipment |
| GET | `/equipment/{id}` | Get one equipment item |
| POST | `/equipment` | Create equipment |

### Reservation API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/reservations` | List reservations |
| GET | `/reservations/{id}` | Get one reservation |
| POST | `/reservations` | Create a reservation |

When a reservation is created, the Reservation API calls the Catalog API programmatically to confirm that the equipment exists and obtain its available quantity.

PostgreSQL advisory locks serialize overlapping reservation requests for the same equipment. This prevents concurrent replicas from overbooking an item.

## Technology

- Python 3.13
- FastAPI
- SQLAlchemy
- PostgreSQL 16
- Nginx
- Docker
- Kubernetes
- Minikube

FastAPI provides input validation and interactive OpenAPI documentation. PostgreSQL provides reliable relational storage and transactions. Docker packages each component consistently. Kubernetes manages deployment, networking, recovery, and scaling.

## Docker Hub images

- `devopspavan02/campuscart-catalog:1.0`
- `devopspavan02/campuscart-reservation:1.0`
- `devopspavan02/campuscart-frontend:1.0`

## Deploy with Minikube

Start Docker Desktop, then start Minikube:

```powershell
minikube start --driver=docker --cpus=2 --memory=3500
```

Create the namespace:

```powershell
kubectl apply -f .\k8s\namespace.yaml
```

Create the database Secret locally:

```powershell
kubectl create secret generic campuscart-db-secret `
  --namespace campuscart `
  --from-literal=postgres-password="campuscart_dev_password" `
  --from-literal=database-url="postgresql+psycopg://campuscart:campuscart_dev_password@postgres:5432/campuscart"
```

The Secret is created separately so credentials are not committed to Git.

Deploy the application:

```powershell
kubectl apply -f .\k8s\campuscart.yaml
kubectl get pods -n campuscart
```

Open the interface:

```powershell
minikube service campuscart-frontend -n campuscart
```

On Windows with the Docker driver, keep this terminal open while accessing the application.

## Independent scaling

Scale only the Catalog API:

```powershell
kubectl scale deployment catalog-api --replicas=3 -n campuscart
kubectl get deployments -n campuscart
```

Return it to its configured size:

```powershell
kubectl scale deployment catalog-api --replicas=2 -n campuscart
```

The Reservation API and database replica counts remain unchanged.

## Persistence demonstration

Create a reservation through the browser and delete the PostgreSQL Pod:

```powershell
kubectl delete pod -n campuscart -l app=postgres
kubectl wait --for=condition=Ready pod -n campuscart -l app=postgres --timeout=120s
```

After refreshing the browser, the reservation remains because the replacement PostgreSQL Pod mounts the same persistent volume.

The Minikube volume survives Pod and Deployment restarts. Deleting the entire Minikube cluster may delete local development storage. A production deployment should use retained storage supplied by a cloud provider.

## Logs

```powershell
kubectl logs -n campuscart -l app=reservation-api --tail=20 --prefix
```

## Security

Implemented controls include:

- API containers run as a non-root numeric user.
- Database credentials are stored in a Kubernetes Secret.
- PostgreSQL and both APIs use internal ClusterIP services.
- Only the frontend is exposed outside the cluster.
- FastAPI validates request fields and types.
- Resource requests and limits reduce resource exhaustion risk.
- Health probes allow Kubernetes to replace unhealthy containers.
- Container dependencies and images use explicit versions.

For production, the system should also use HTTPS through an Ingress controller, user authentication, role-based authorization, NetworkPolicies, rate limiting, automated image scanning, database backups, and an external secret manager.

The demonstration uses a simple password and HTTP because it runs on an isolated local Minikube cluster.

## Repository structure

```text
campuscart/
├── catalog-service/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── reservation-service/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile
│   ├── index.html
│   └── nginx.conf
├── k8s/
│   ├── campuscart.yaml
│   └── namespace.yaml
├── docs/
├── .gitignore
└── README.md
```

## Current limitations

CampusCart is intentionally small for an academic demonstration. Its current workload does not economically require microservices. The assumed business scenario is deployment across several campuses, where equipment browsing and reservation traffic grow at different rates.

Using microservices adds deployment, monitoring, networking, and data-management complexity. The design becomes useful at larger scale because teams can deploy and scale Catalog and Reservation capabilities independently.