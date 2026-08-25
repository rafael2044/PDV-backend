from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.dependencies import get_current_user, allow_admin_only
from app.config import settings
from app import models

router = APIRouter(prefix="/settings", tags=["Settings"])

# Estado global do NFC-e (permite alteração em tempo real sem reiniciar)
_nfce_habilitado_cache = settings.NFCE_HABILITADO


def get_nfce_habilitado() -> bool:
    """Retorna o estado atual do NFC-e (cache em memória)."""
    return _nfce_habilitado_cache


class NFCeConfigUpdate(BaseModel):
    nfce_habilitado: Optional[bool] = None
    nfce_ambiente: Optional[int] = None
    nfce_uf: Optional[str] = None
    nfce_serie: Optional[str] = None
    nfce_municipio_ibge: Optional[str] = None
    nfce_certificado_caminho: Optional[str] = None
    nfce_certificado_senha: Optional[str] = None
    nfce_csc: Optional[str] = None
    nfce_id_csc: Optional[str] = None


@router.get("/")
async def get_settings(
    current_user: models.User = Depends(get_current_user)
):
    """Retorna as configurações do sistema (sem dados sensíveis)."""
    return {
        "nome_fantasia": settings.NOME_FANTASIA,
        "cnpj": settings.CNPJ,
        "nfce": {
            "habilitado": get_nfce_habilitado(),
            "ambiente": settings.NFCE_AMBIENTE,
            "uf": settings.NFCE_UF,
            "serie": settings.NFCE_SERIE,
            "municipio_ibge": settings.NFCE_MUNICIPIO_IBGE,
            "certificado_configurado": bool(settings.NFCE_CERTIFICADO_CAMINHO),
            "csc_configurado": bool(settings.NFCE_CSC)
        }
    }


def _salvar_env(key: str, value: str):
    """Salva uma variável no arquivo .env."""
    from pathlib import Path
    
    env_path = Path(__file__).parent.parent.parent / ".env"
    
    if not env_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Arquivo .env não encontrado."
        )
    
    with open(env_path, "r") as f:
        content = f.read()
    
    import re
    if key in content:
        content = re.sub(
            rf'{key}=.*',
            f'{key}={value}',
            content
        )
    else:
        content += f"\n{key}={value}\n"
    
    with open(env_path, "w") as f:
        f.write(content)


@router.put("/nfce", dependencies=[Depends(allow_admin_only)])
async def update_nfce_config(
    config: NFCeConfigUpdate,
    current_user: models.User = Depends(get_current_user)
):
    """
    Atualiza as configurações do NFC-e.
    """
    from pathlib import Path
    
    env_path = Path(__file__).parent.parent.parent / ".env"
    
    if not env_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Arquivo .env não encontrado."
        )
    
    # Ler conteúdo atual
    with open(env_path, "r") as f:
        lines = f.readlines()
    
    # Mapear configurações para variáveis de ambiente
    config_map = {
        "nfce_habilitado": "NFCE_HABILITADO",
        "nfce_ambiente": "NFCE_AMBIENTE",
        "nfce_uf": "NFCE_UF",
        "nfce_serie": "NFCE_SERIE",
        "nfce_municipio_ibge": "NFCE_MUNICIPIO_IBGE",
        "nfce_certificado_caminho": "NFCE_CERTIFICADO_CAMINHO",
        "nfce_certificado_senha": "NFCE_CERTIFICADO_SENHA",
        "nfce_csc": "NFCE_CSC",
        "nfce_id_csc": "NFCE_ID_CSC"
    }
    
    # Atualizar valores
    updated_vars = {}
    for field, env_var in config_map.items():
        value = getattr(config, field, None)
        if value is not None:
            updated_vars[env_var] = str(value).lower() if isinstance(value, bool) else str(value)
    
    # Reescrever arquivo .env
    new_lines = []
    updated_keys = set()
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            key = line.split("=")[0].strip()
            if key in updated_vars:
                new_lines.append(f"{key}={updated_vars[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line + "\n")
        else:
            new_lines.append(line + "\n")
    
    # Adicionar variáveis que não existiam
    for key, value in updated_vars.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")
    
    # Salvar arquivo
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    
    # Atualizar cache em memória se NFCE_HABILITADO foi alterado
    global _nfce_habilitado_cache
    if "NFCE_HABILITADO" in updated_vars:
        _nfce_habilitado_cache = updated_vars["NFCE_HABILITADO"] == "true"
    
    return {
        "success": True,
        "message": "Configurações NFC-e atualizadas.",
        "updated": list(updated_vars.keys())
    }


@router.post("/nfce/toggle")
async def toggle_nfce(
    current_user: models.User = Depends(allow_admin_only)
):
    """Alterna rapidamente o status de habilitação do NFC-e."""
    global _nfce_habilitado_cache
    
    # Alternar valor
    new_value = not _nfce_habilitado_cache
    
    # Atualizar no arquivo .env
    _salvar_env("NFCE_HABILITADO", str(new_value).lower())
    
    # Atualizar cache em memória
    _nfce_habilitado_cache = new_value
    
    return {
        "success": True,
        "nfce_habilitado": new_value,
        "message": f"NFC-e {'habilitado' if new_value else 'desabilitado'} com sucesso!"
    }
