from rest_framework import status
from rest_framework.response import Response


def success_response(data=None, message=None, status_code=status.HTTP_200_OK):
    payload = {"success": True}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    return Response(payload, status=status_code)


def error_response(errors, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {"success": False, "errors": errors},
        status=status_code,
    )
