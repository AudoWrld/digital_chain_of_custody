from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Conversation, Message


@login_required
def index(request):
    # list conversations for current user
    convs = request.user.conversations.all()
    return render(request, "chat/index.html", {"conversations": convs})


@login_required
def room(request, conversation_id):
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if request.user not in conv.participants.all():
        # simple guard: add user to participants so they can join
        conv.participants.add(request.user)

    messages = conv.messages.all().select_related("sender")[:100]
    return render(request, "chat/room.html", {"conversation": conv, "messages": messages})
