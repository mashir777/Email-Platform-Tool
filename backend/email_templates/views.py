from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error_response, success_response
from email_templates.models import MessagePurpose, MessageVersion
from email_templates.serializers import (
    MessagePurposeCreateSerializer,
    MessagePurposeSerializer,
    MessageVersionSerializer,
)

DEFAULT_PURPOSES = (
    "Employee Augmentation",
    "SaaS Work",
    "Custom Software Development",
)

# Properly spaced plain-text templates — newlines become readable email paragraphs on send.
DEFAULT_MESSAGE_CONTENT = {
    "Employee Augmentation": {
        "v1": {
            "subject": "Need skilled developers without hiring overhead?",
            "html_content": (
                "Hi {{name}},\n\n"
                "I was looking at {{Company Name}}'s recent growth and was wondering how your team is currently "
                "handling development capacity.\n\n"
                "At Datrix World (datrixworld.com), we help companies scale with dedicated engineers — frontend, "
                "backend, and full-stack — without the cost of building a full in-house team.\n\n"
                "If {{Company Name}} needs extra hands for delivery, product launches, or backlog cleanup, we can "
                "embed experienced developers quickly.\n\n"
                "Worth a brief, no-pressure chat next week?\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
        "v2": {
            "subject": "Flexible engineers for {{Company Name}}",
            "html_content": (
                "Hi {{name}},\n\n"
                "Quick question — is {{Company Name}} still short on engineering bandwidth for upcoming work?\n\n"
                "Datrix World (datrixworld.com) provides Employee Augmentation so teams can add vetted developers "
                "on demand and keep delivery moving.\n\n"
                "Most {{Industrial Company}} companies use this when hiring is too slow or too expensive.\n\n"
                "Happy to share how similar teams are doing it if useful.\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
        "v3": {
            "subject": "Scale your team with Datrix World",
            "html_content": (
                "Hi {{name}},\n\n"
                "As {{Company Name}} grows, adding temporary or project-based developers can save months of hiring time.\n\n"
                "At Datrix World (datrixworld.com), we specialize in Employee Augmentation — placing skilled remote "
                "engineers who work as an extension of your team.\n\n"
                "Would it help to see a short overview of roles we can fill for {{Industrial Company}} teams?\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
    },
    "SaaS Work": {
        "v1": {
            "subject": "Building or scaling a SaaS product?",
            "html_content": (
                "Hi {{name}},\n\n"
                "I was looking at {{Company Name}}'s recent growth and was wondering how you are currently managing "
                "your custom software needs.\n\n"
                "At Datrix World (datrixworld.com), we help companies build robust, scalable SaaS products and custom "
                "web applications without the overhead of maintaining an expensive in-house development team.\n\n"
                "Are you currently facing any bottlenecks with your tech stack, or planning to launch a new digital "
                "product soon?\n\n"
                "I'd love to share a couple of ideas that worked well for similar brands. Worth a brief, no-pressure "
                "chat next week?\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
        "v2": {
            "subject": "SaaS product help for {{Company Name}}",
            "html_content": (
                "Hi {{name}},\n\n"
                "Quick thought for {{Company Name}} — if you're building or improving a SaaS product, Datrix World "
                "(datrixworld.com) can help with architecture, development, and shipping features faster.\n\n"
                "We work with {{Industrial Company}} companies that want a reliable engineering partner instead of "
                "hiring a full internal product team.\n\n"
                "Would a short call next week be useful to compare approaches?\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
        "v3": {
            "subject": "Launch faster with Datrix World",
            "html_content": (
                "Hi {{name}},\n\n"
                "Many {{Industrial Company}} teams at the {{Company Name}} stage lose time between product ideas and "
                "release.\n\n"
                "At Datrix World (datrixworld.com), we build SaaS platforms end-to-end — UI, APIs, billing, "
                "integrations, and ongoing improvements.\n\n"
                "If you're considering outsourcing product development, I can share a clear plan and timeline.\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
    },
    "Custom Software Development": {
        "v1": {
            "subject": "Custom software built for {{Company Name}}",
            "html_content": (
                "Hi {{name}},\n\n"
                "I noticed {{Company Name}} and wanted to ask whether your team is currently handling all software "
                "development in-house.\n\n"
                "At Datrix World (datrixworld.com), we build custom software for companies around the world — "
                "web apps, portals, dashboards, and business systems tailored to each workflow.\n\n"
                "If {{Company Name}} needs a trusted partner to design and develop software, happy to share how we "
                "usually start.\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
        "v2": {
            "subject": "Let Datrix World build your software",
            "html_content": (
                "Hi {{name}},\n\n"
                "Quick question — is {{Company Name}} exploring a new internal tool, customer portal, or custom "
                "application this quarter?\n\n"
                "Datrix World (datrixworld.com) helps {{Industrial Company}} organizations turn requirements into "
                "production-ready software without hiring a full engineering team.\n\n"
                "Would it help to see examples from similar projects?\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
        "v3": {
            "subject": "Software development partnership with Datrix World",
            "html_content": (
                "Hi {{name}},\n\n"
                "As {{Company Name}} grows, custom software often becomes the fastest way to improve operations "
                "and customer experience.\n\n"
                "At Datrix World (datrixworld.com), we partner with companies worldwide as their development team — "
                "from discovery and design through build, launch, and support.\n\n"
                "Open to a brief conversation to see if we're a fit?\n\n"
                "Best regards,\n"
                "Oliver Wilson\n"
                "Datrix World"
            ),
        },
    },
}


def _ensure_versions(purpose):
    for version, _label in MessageVersion.Version.choices:
        defaults = DEFAULT_MESSAGE_CONTENT.get(purpose.name, {}).get(version, {})
        message_version, _created = MessageVersion.objects.get_or_create(
            purpose=purpose,
            version=version,
            defaults={
                "subject": defaults.get("subject", ""),
                "html_content": defaults.get("html_content", ""),
            },
        )
        update_fields = []
        if not (message_version.subject or "").strip() and defaults.get("subject"):
            message_version.subject = defaults["subject"]
            update_fields.append("subject")
        if not (message_version.html_content or "").strip() and defaults.get("html_content"):
            message_version.html_content = defaults["html_content"]
            update_fields.append("html_content")
        if update_fields:
            update_fields.append("updated_at")
            message_version.save(update_fields=update_fields)


def _ensure_default_purposes(owner):
    for name in DEFAULT_PURPOSES:
        purpose, _created = MessagePurpose.objects.get_or_create(owner=owner, name=name)
        _ensure_versions(purpose)


class MessagePurposeCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_default_purposes(request.user)
        purposes = (
            MessagePurpose.objects.filter(owner=request.user)
            .prefetch_related("versions")
            .order_by("name")
        )
        return success_response(
            data={"purposes": MessagePurposeSerializer(purposes, many=True).data},
        )

    @transaction.atomic
    def post(self, request):
        serializer = MessagePurposeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)
        name = serializer.validated_data["name"].strip()
        if MessagePurpose.objects.filter(owner=request.user, name__iexact=name).exists():
            return error_response(
                {"name": ["A message purpose with this name already exists."]},
                status.HTTP_400_BAD_REQUEST,
            )
        purpose = MessagePurpose.objects.create(owner=request.user, name=name)
        _ensure_versions(purpose)
        purpose = MessagePurpose.objects.prefetch_related("versions").get(pk=purpose.pk)
        return success_response(
            data={"purpose": MessagePurposeSerializer(purpose).data},
            message="Message purpose created.",
            status_code=status.HTTP_201_CREATED,
        )


class MessagePurposeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, purpose_id):
        return get_object_or_404(MessagePurpose, id=purpose_id, owner=request.user)

    def patch(self, request, purpose_id):
        purpose = self.get_object(request, purpose_id)
        serializer = MessagePurposeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)
        name = serializer.validated_data["name"].strip()
        if (
            MessagePurpose.objects.filter(owner=request.user, name__iexact=name)
            .exclude(pk=purpose.pk)
            .exists()
        ):
            return error_response(
                {"name": ["A message purpose with this name already exists."]},
                status.HTTP_400_BAD_REQUEST,
            )
        purpose.name = name
        purpose.save(update_fields=["name", "updated_at"])
        return success_response(
            data={"purpose": MessagePurposeSerializer(purpose).data},
            message="Message purpose updated.",
        )

    def delete(self, request, purpose_id):
        purpose = self.get_object(request, purpose_id)
        purpose.delete()
        return success_response(message="Message purpose deleted.")


class MessageVersionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, version_id):
        version = get_object_or_404(
            MessageVersion.objects.select_related("purpose"),
            id=version_id,
            purpose__owner=request.user,
        )
        serializer = MessageVersionSerializer(version, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(serializer.errors, status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return success_response(
            data={"version": serializer.data},
            message="Message version updated.",
        )
