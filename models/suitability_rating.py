from pydantic import BaseModel, Field

class SuitabilityRating(BaseModel):
    suitability_score: str = Field(description="A score between 0 and 100 indicating the suitability of the job post for the company")
    reason: str = Field(description="A detailed explanation of the suitability score. Max 2 sentences.")