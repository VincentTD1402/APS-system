from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    """Single LLM endpoint configuration."""

    name: str = "default"
    model_name: str = "Qwen/Qwen3-4B"
    api_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 30
    streaming: bool = True
    thinking: bool = False


class LLMSettings(BaseSettings):
    """LLM settings — supports multiple named configs (think / no_think).

    Env var pattern (pydantic-settings nested delimiter '__'):
        LLM_LLM_CONFIGS__THINK__API_URL=http://...
        LLM_LLM_CONFIGS__THINK__THINKING=true
        LLM_LLM_CONFIGS__NO_THINK__MAX_TOKENS=4096
    """

    LLM_CONFIGS: dict[str, LLMConfig] = Field(
        default={
            "think":    LLMConfig(name="think",    thinking=True,  temperature=0.6),
            "no_think": LLMConfig(name="no_think", thinking=False, temperature=0.7),
        }
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LLM_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    def get_llm_config(self, name: str = "no_think") -> LLMConfig:
        """Return config by name; raises ValueError if not found or api_url empty."""
        cfg = self.LLM_CONFIGS.get(name)
        if cfg is None:
            raise ValueError(
                f"LLM config '{name}' not found. Available: {list(self.LLM_CONFIGS)}"
            )
        if not cfg.api_url:
            raise ValueError(
                f"LLM config '{name}' has empty api_url. "
                f"Set LLM_LLM_CONFIGS__{name.upper()}__API_URL env var."
            )
        return cfg


class Settings(BaseSettings):
    """Application settings"""

    # APS Database
    APS_DB_URL: str = ""

    # Application
    API_VERSION: str = "v1"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # LLM — lazy init; reads LLM_* env vars independently
    LLM: LLMSettings = Field(default_factory=LLMSettings)

    # G-System Configuration

    ## G-System DB
    GSYSTEM_DB_URL: str = ""
    GSYSTEM_DB_USER: str = ""
    GSYSTEM_DB_PASSWORD: str = ""
    
    ## G-System API
    GSYSTEM_BASE_URL: str = ""
    GSYSTEM_API_KEY: str = ""
    GSYSTEM_TIMEOUT: float = 30.0
    GSYSTEM_RETRIES: int = 3
    GSYSTEM_ALL_DATA: bool = False  # testing only — adds allDataYn="Y" to fetch requests
    # Production area for MPS plan sync (GET /pd/prodPlanMpsMng?pareaId=) — single-parea deployments use 1
    GSYSTEM_DEFAULT_PAREA_ID: int = 1

    # G-System sync on a schedule (same lock as POST /gsystem/run — only one sync at a time).
    # Cron format: APScheduler `CronTrigger.from_crontab` — 5 fields (minute hour day month day_of_week).
    # Example: "0 3 * * 0" = every Sunday at 03:00 (see APScheduler CronTrigger docs).
    # Use uvicorn --workers 1 when enabled; multiple workers would run duplicate jobs.
    GSYSTEM_SYNC_CRON_ENABLED: bool = False
    GSYSTEM_SYNC_CRON: str = "0 3 * * 0"
    GSYSTEM_SYNC_CRON_TIMEZONE: str = "UTC"

    # Purchase request defaults used by CREATE_PURCHASE_REQUEST
    PURCHASE_REQ_CORP_ID: int = 1
    PURCHASE_REQ_CUST_ID: int = 100
    PURCHASE_REQ_DEPT_ID: int = 36
    PURCHASE_REQ_EMP_ID: int = 166
    PURCHASE_REQ_REMARK: str = "purchase request from AI"

    # Workorder defaults (can be set via env vars)
    WORKORDER_DEFAULT_BIZ_ID: int = 7
    WORKORDER_DEFAULT_CORP_ID: int = 1
    WORKORDER_DEFAULT_DEPT_ID: int = 153
    WORKORDER_DEFAULT_STOCK_YN: str = "false"
    WORKORDER_DEFAULT_CNTU_PROC_YN: str = "false"
    WORKORDER_DEFAULT_CNTU_PROC_ORD: str = ""
    WORKORDER_DEFAULT_DELV_TYPE: str = ""

    # Horizons & calendar — IANA timezone for shift start / day boundaries
    APS_CALENDAR_TIMEZONE: str = "UTC"

    # KPI Summary — Default workcenter capacity in minutes per day (8 hours = 480 minutes)
    DEFAULT_CAPACITY_MINUTES: float = 480.0

    # KPI Summary — Risk thresholds
    # R1: Delivery compliance rate threshold (percentage). Risk triggered if rate < threshold.
    KPI_R1_COMPLIANCE_THRESHOLD: float = 100.0
    # R3: Workcenter load threshold (percentage). Risk triggered if load > threshold.
    KPI_R3_OVERLOAD_THRESHOLD: float = 100.0

    # Neo4j Configuration
    APS_NEO4J_URI: str = ""
    APS_NEO4J_USER: str = "APS_neo4j"
    APS_NEO4J_PASSWORD: str = ""
    APS_NEO4J_DATABASE: str = "neo4j"
    # Neo4j 5+ GQL hints (unknown label/property keys) — silence for cleaner logs during dev/partial import.
    APS_NEO4J_SILENCE_NOTIFICATIONS: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", 
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()

