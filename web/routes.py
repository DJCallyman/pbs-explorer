from fastapi import APIRouter

from web.helpers import *  # noqa: F401,F403

router = APIRouter(include_in_schema=False)
