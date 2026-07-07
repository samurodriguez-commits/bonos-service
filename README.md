# bonos-service

Microservicio de **bonos y promociones** del casino (FastAPI). Comparte la base de
datos PostgreSQL y el `JWT_SECRET` con `casino-backend` (valida el JWT del backend,
no tiene login propio). Ofrece bonos (bienvenida, recarga, cashback) que acreditan
saldo y registran la transacción.

- Prefijo de rutas: `/api/bonos` · Docs: `/docs`

## Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/bonos` | Bonos disponibles |
| GET | `/api/bonos/mis-bonos` | Bonos reclamados por el usuario |
| POST | `/api/bonos/{codigo}/reclamar` | Reclamar un bono (acredita saldo) |

## Ejecutar en local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# variables: copia .env.example a .env y ajústalas
uvicorn app.main:app --reload --port 8004
```
Requiere una PostgreSQL accesible con las tablas compartidas (`usuarios`,
`transacciones`) que crea `casino-backend`.

## Entrega (lo que debes implementar)
1. **Rutas de salud** para Kubernetes (ver el `TODO` en `app/main.py`):
   *liveness* (¿el proceso vive?) y *readiness* (¿listo para tráfico? verifica la BD, responde 200/503).
2. **Dockerfile** para contenerizar el servicio.
3. **Workflow de CI/CD** (GitHub Actions) que construya la imagen, la publique en ECR y despliegue en **EKS**.
4. **Manifiestos de Kubernetes** (Deployment + Service) con las probes apuntando a tus rutas de salud.
5. **Pruebas de carga** que evidencien el correcto funcionamiento en EKS (escalado, disponibilidad).
