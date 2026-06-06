from pydantic import BaseModel, EmailStr, Field

from codrut.contracts.emails import EmailDeliveryStatus, EmailProviderKey


class EmailTestSendRequest(BaseModel):
    to: EmailStr
    subject: str = Field(default="Test Codrut email", min_length=1, max_length=180)
    html_body: str = Field(default="<p>Test email din Codrut.</p>", min_length=1)
    text_body: str = Field(default="Test email din Codrut.", min_length=1)


class EmailTestSendResponse(BaseModel):
    provider: EmailProviderKey
    status: EmailDeliveryStatus
    message_id: str
    recipient: EmailStr
