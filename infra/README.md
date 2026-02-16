# Infraestructura — AWS Lambda

El scraper se despliega como una **AWS Lambda con container image** y se expone via **Function URL** (sin API Gateway).

## Arquitectura

```
ETL (otro proyecto)
      │
      │  POST /product
      ▼
Lambda Function URL ──► Playwright + FastAPI (container)
                              │
                              ▼
                        gate.decodo.com (proxy residencial)
                              │
                              ▼
                        mercadolibre.com.co
                              │
                              ▼
                        JSON response
```

## Recursos en AWS (Terraform)

| Recurso | Nombre | Descripción |
|---|---|---|
| ECR Repository | `meli-scrapper` | Registry privado para las imágenes Docker |
| IAM Role | `meli-scrapper-lambda-role` | Rol con permisos de CloudWatch Logs |
| Lambda Function | `meli-scrapper` | 2048MB RAM, 900s timeout, imagen desde ECR |
| Function URL | (auto-generada) | URL pública con auth type NONE |
| Lambda Permission | `FunctionURLAllowPublicAccess` | Permite invocación pública via Function URL |

## Archivos

```
infra/
├── main.tf          # Todos los recursos AWS
├── variables.tf     # Variables configurables (region, memoria, timeout)
├── outputs.tf       # Outputs: function_url, function_name, ecr_repository_url
└── README.md        # Este archivo
```

## Setup inicial (una sola vez)

```bash
cd infra
terraform init
terraform apply
```

Esto crea toda la infra. La primera vez necesitás pushear código a master para que GitHub Actions suba la imagen a ECR, y luego correr `terraform apply` para que Lambda la tome.

Después de esto, hay que agregar un segundo permiso para que la Function URL sea accesible públicamente (requerido desde octubre 2025):

```bash
aws lambda add-permission \
  --function-name meli-scrapper \
  --statement-id "FunctionURLAllowPublicInvoke" \
  --action "lambda:InvokeFunction" \
  --principal "*" \
  --region us-east-1
```

Terraform ya crea el permiso `lambda:InvokeFunctionUrl`, pero desde octubre 2025 Lambda requiere también `lambda:InvokeFunction` para que las Function URLs funcionen.

## Variables de entorno en Lambda

Configuradas manualmente (no en Terraform para no exponer credenciales en código):

| Variable | Descripción |
|---|---|
| `PROXY_USER` | Usuario de Decodo (ex-Smartproxy) |
| `PROXY_PASSWORD` | Password de Decodo |

```bash
aws lambda update-function-configuration \
  --function-name meli-scrapper \
  --environment "Variables={PROXY_USER=xxx,PROXY_PASSWORD=xxx}" \
  --region us-east-1
```

## Destruir todo

```bash
cd infra
terraform destroy
```

## CI/CD — `.github/workflows/deploy-lambda.yml`

Se ejecuta en cada push a `master` (o manualmente via `workflow_dispatch`).

### Pasos:

1. **Checkout** — clona el repo
2. **Configure AWS credentials** — usa `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` de los secrets del repo
3. **Login to ECR** — obtiene token temporal para autenticar Docker contra el registry privado
4. **Build, tag, push** — construye `Dockerfile.lambda` con `--platform linux/amd64` y `--provenance=false` (Lambda no acepta manifiestos OCI index), tagea con el SHA del commit + `latest`, y pushea ambos tags a ECR
5. **Update Lambda** — ejecuta `update-function-code` para que Lambda use la nueva imagen, y espera a que termine de actualizar

### Secrets necesarios en GitHub (Settings → Secrets → Actions):

| Secret | Descripción |
|---|---|
| `AWS_ACCESS_KEY_ID` | Access key de IAM |
| `AWS_SECRET_ACCESS_KEY` | Secret key de IAM |

## Costos estimados

| Concepto | Costo/mes |
|---|---|
| Lambda (1 ejecución/día) | ~$0.72 |
| ECR (storage imagen) | ~$0.10 |
| Proxy Decodo (~2.25GB) | ~$8.00 |
| **Total** | **~$9/mes** |
