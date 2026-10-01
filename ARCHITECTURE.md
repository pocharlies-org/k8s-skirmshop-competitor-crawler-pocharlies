# ARCHITECTURE — k8s-skirmshop-competitor-crawler-pocharlies

Repo: `pocharlies-org/k8s-skirmshop-competitor-crawler-pocharlies` · tronco real: `main` (default branch del survey) · workflows `ci.yml`, `pr-review.yml`.
Esqueleto GitOps **desactivado** del crawler de competencia de Skirmshop (`replicas: 0`). **No hay ninguna Application de ArgoCD que apunte a este repo** (el survey del devops verificó los repoURL de las ~90 apps): hoy no despliega nada. Es candidato a abandono (C5).
**Repo de aplicación:** la imagen `harbor.e-dani.com/homelab/skirmshop-competitor-crawler:pending` viene del compose de sauvage (`/home/ubuntu/skirmshop/skirmshop-competitor-crawler`, README); no existe repo de código en la lista de la tanda ni clon en `~/k8s` (no localizado). El ciclo de vida de la competencia hoy está en `skirmshopshopifyapp` (`app/routes/api.competitors.*`, `app/services/competitors/`) y en el cerebro.

## Clientes y versiones
- Sin clientes. Un único `Deployment` `skirmshop-competitor-crawler` (`k8s/manifest.yaml`): `replicas: 0`, nodo `role: edge` amd64 con su toleration, `automountServiceAccountToken: false`, límite 1 Gi. Etiqueta de kustomize `e-dani.com/activation: disabled`.
- Imagen: `…/skirmshop-competitor-crawler:pending` (tag placeholder: no existe imagen construida).

## Dependencias en ambos sentidos
- Depende de (variables del manifiesto): cerebro (`BRAIN_URL=http://skirmshop-brain.skirmshop-brain-prod.svc.cluster.local`, `BRAIN_INSTANCE=skirmshop`), Firecrawl (`FIRECRAWL_URL=http://firecrawl-api.skirmshop.svc.cluster.local:3002`; ver `skirmshop-firecrawl`), Secret opcional `competitor-crawler-secrets`, Secret `harbor-pull`.
- De él dependen: nadie (está apagado). El panel lo describe como «motor headless, `replicas:0`, sin HTTP» y propone observarlo vía brain (`skirmshop-control-panel/00-ARQUITECTURA.md`).
- El README declara que sigue desactivado «hasta confirmar límites de tasa, imagen de origen e instancia de brain destino»: ninguna de las tres cosas se ha confirmado en este repo.

## Stack con versiones
- Kustomize (`namespace: skirmshop`, un solo recurso). Sin imágenes pineadas por digest (`:pending`). Sin Helm.

## Componentes compartidos
- Publica: nada activo. Consume: las URLs del cerebro y de Firecrawl.
- Antes de reactivarlo hay que decidir el repo de código y la imagen (hoy inexistentes) y comprobar que no duplica la lógica de competidores de `skirmshopshopifyapp` (`api.competitors.$id.sync-start|sync-result|sync-heartbeat`, que ya modelan un runner externo que sincroniza fuentes).

## Cómo se construye
- No se construye nada: es un esqueleto. Para activarlo haría falta: repo con Dockerfile y release a Harbor, tag/digest real, `replicas` > 0, Secret `competitor-crawler-secrets`, y una Application de ArgoCD que apunte a este repo (rama `main`).

## Tests
- Solo validación de manifiestos: `ci.yml` → `reusable-ci.yml@main` de `k8s-gitops-pocharlies` (`arc-k8s`, `run_node: false`, `run_docker_build: false`, `kustomize_paths: ". k8s"`).

## CI/CD y despliegue
- Tronco `main`; **sin Application de ArgoCD** (no hay `targetRevision`). Nada se sincroniza; un merge aquí no cambia el clúster. Verificación: `kubectl get applications -n argocd -o json` buscando este `repoURL` (devops, survey).

## Decisiones y trampas
- «Merged» aquí no significa «desplegado»: sin Application, el repo es solo documentación de intención.
- `activation: disabled` y `replicas: 0` son deliberados; no cambiarlos sin decisión de negocio (límites de tasa de competidores y coste de Firecrawl).
- El tag `:pending` fallaría el pull si alguien subiera réplicas.

## Referencias cruzadas
- App del dominio de competencia: `skirmshopshopifyapp` (rutas `api.competitors.*`); extracción web: `skirmshop-firecrawl`; destino de datos: `skirmshop-brain-v2`; panel: `skirmshop-control-panel` (vista Competencia, lee de brain).

## Hallazgo C5 (propuesta, sin archivar)
- **Abandono probable:** sin Application, imagen `:pending`, `replicas: 0` y sin repo de código localizable. Propuesta: archivar el repo o, si el crawler se retoma, crear el repo de aplicación y la Application primero. No se archiva en esta épica.
