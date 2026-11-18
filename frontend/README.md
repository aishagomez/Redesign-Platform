# Frontend

Consola web en React + Vite para autenticacion, monitoreo, composicion y seguimiento de pipelines.

## Funcionalidades actuales

- login y registro de usuarios;
- dashboard con KPIs y ejecuciones recientes;
- gestion de proyectos y pipelines;
- compositor de ejecuciones por etapas;
- explorador de herramientas importadas;
- monitoreo de workers;
- inspeccion de salidas y logs de stages.

## Archivos clave

- [src/App.jsx](src/App.jsx): rutas y paginas.
- [src/api.js](src/api.js): cliente HTTP.
- [src/components.jsx](src/components.jsx): layout y componentes reutilizables.
- [src/styles.css](src/styles.css): estilos globales.

## Scripts

```bash
npm install
npm run dev
npm run build
```

## Variable de entorno

- `VITE_API_BASE_URL`: URL base de la API.

## Limitaciones actuales

- no hay testing automatizado;
- el diagnostico visual y los errores de red siguen siendo bastante crudos;
- la consola esta mas cerca de un panel operativo que de una experiencia pulida para onboarding de usuarios finales.
