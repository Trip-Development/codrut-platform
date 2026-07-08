from pydantic import BaseModel, ConfigDict


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
