// Espelha o backend: GET /api/v1/health (api/main.py + api/health.py). STORY-00-06.
export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  // Checks de componentes plugáveis (00-03 postgres, 00-04 redis).
  postgres?: string;
  redis?: string;
}
