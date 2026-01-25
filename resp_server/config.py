from dataclasses import dataclass

@dataclass
class ServerConfig:
    host: str = "localhost"
    port: int = 6379
    rdb_dir: str = "."
    db_filename: str = "dump.rdb"

# Global config instance
config = ServerConfig()
