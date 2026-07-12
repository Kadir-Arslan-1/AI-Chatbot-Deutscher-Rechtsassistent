from pydantic import BaseModel, Field

class BotResponse(BaseModel):
    explanation: str = Field(description="The easy-to-understand answer for the user.")
    cited_laws: list[str] = Field(description="A list of specific laws cited, e.g., ['§ 87 BetrVG'].")
    is_information_missing: bool = Field(description="True if the context didn't have enough info.")