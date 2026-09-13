# CampusCart Video Demonstration

Target length: 6–8 minutes.

## Preparation

Keep the frontend tunnel running:

```powershell
minikube service campuscart-frontend -n campuscart
```

Use another terminal for demonstration commands.

## 0:00–0:45 — Introduction

Show the browser interface.

“CampusCart is a university equipment reservation application built with Python, FastAPI, PostgreSQL, Docker, Nginx, and Kubernetes. Students can browse equipment and reserve it for selected dates. The project demonstrates REST communication, independent scaling, persistent storage, and external Kubernetes access.”

## 0:45–1:30 — Architecture

Show the diagram in `README.md`.

“The browser connects to the Nginx frontend and API gateway. Equipment requests go to the Catalog REST API. Booking requests go to the Reservation REST API. Reservation calls Catalog programmatically to validate the equipment before writing the booking to PostgreSQL. PostgreSQL uses persistent Kubernetes storage.”

## 1:30–2:20 — User interface

Create a reservation through the browser.

“The equipment was loaded from the Catalog API. This reservation travels through the frontend gateway to the Reservation API. Reservation calls Catalog, checks overlapping quantities, and saves the booking in PostgreSQL.”

## 2:20–3:10 — REST APIs

Run:

```powershell
kubectl port-forward service/catalog-api 8000:8000 -n campuscart
```

Show `http://localhost:8000/docs`, then stop with **Ctrl+C**.

Run:

```powershell
kubectl port-forward service/reservation-api 8001:8000 -n campuscart
```

Show `http://localhost:8001/docs`, then stop with **Ctrl+C**.

“These interactive OpenAPI pages show that both microservices provide REST APIs.”

## 3:10–4:00 — Kubernetes resources

Run:

```powershell
kubectl get deployments -n campuscart
kubectl get services -n campuscart
kubectl get pvc -n campuscart
```

“Catalog, Reservation, and frontend each have two replicas. PostgreSQL has one replica. Only the frontend uses NodePort. The APIs and database remain internal. The bound volume claim stores PostgreSQL data.”

## 4:00–4:45 — Independent scaling

Run:

```powershell
kubectl scale deployment catalog-api --replicas=3 -n campuscart
kubectl rollout status deployment/catalog-api -n campuscart
kubectl get deployments -n campuscart
```

“Only Catalog increased to three replicas. Reservation stayed at two and PostgreSQL stayed at one, proving independent horizontal scaling.”

Return it to two:

```powershell
kubectl scale deployment catalog-api --replicas=2 -n campuscart
```

## 4:45–5:40 — Persistence

Show an existing reservation, then run:

```powershell
kubectl delete pod -n campuscart -l app=postgres
kubectl wait --for=condition=Ready pod -n campuscart -l app=postgres --timeout=120s
```

Refresh the browser.

“The database Pod was replaced, but the reservation remains because the new Pod mounted the same persistent volume.”

## 5:40–6:20 — Logs and YAML

Run:

```powershell
kubectl logs -n campuscart -l app=reservation-api --tail=20 --prefix
```

Briefly show `k8s/campuscart.yaml`, including replica counts, images, probes, resource limits, Services, NodePort, and the persistent volume claim.

## 6:20–7:00 — Security and business conclusion

“The implementation uses input validation, non-root API containers, internal services, resource limits, health probes, and a Kubernetes Secret that is not committed to Git.

Production would also require HTTPS, authentication, authorization, NetworkPolicies, managed secrets, monitoring, and database backups.

This demonstration is too small to economically require microservices. The assumed business case is expansion across several campuses where browsing and booking traffic scale differently. Independent scaling and deployment provide flexibility, while extra networking, infrastructure, and monitoring create additional cost and complexity.”