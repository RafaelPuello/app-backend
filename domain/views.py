from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from nfctags import get_nfctag_model
from nfctags.validators import is_valid_uuid

from .forms import BasePlantLabelForm
from .services import NFCTagService
from .selectors import get_nfctags_for

NFCTag = get_nfctag_model()


@never_cache
def list_nfctags(request):
    context = {}

    queried_uuid = request.GET.get('uuid')
    if queried_uuid:
        if is_valid_uuid(queried_uuid):
            try:
                context.update({"queried_nfctag": NFCTag.objects.get(uuid=queried_uuid)})
                return render(request, "domain/index.html", context)
            except NFCTag.DoesNotExist:
                messages.error(request, _("The requested NFC tag does not exist."))
        else:
            messages.error(request, _("Invalid UUID format."))

    if request.user.is_authenticated:
        context.update({"nfctags": get_nfctags_for(fetched_by=request.user)})

    return render(request, "domain/index.html", context)


@login_required
@never_cache
def detail_nfctag(request, nfctag_uuid):
    nfctag = get_object_or_404(get_nfctags_for(fetched_by=request.user), uuid=nfctag_uuid)
    return render(request, "domain/detail.html", {"nfctag": nfctag})


@login_required
@never_cache
def edit_nfctag(request, nfctag_uuid):
    nfctag = get_object_or_404(get_nfctags_for(fetched_by=request.user), uuid=nfctag_uuid)

    if request.method == "POST":
        form = BasePlantLabelForm(request.POST, instance=nfctag)

        if form.is_valid():
            nfctag = form.save()
            messages.success(request, _('NFC Tag successfully updated.'))
            return redirect(reverse('domain:detail_nfctag', args=[nfctag_uuid]))

    else:
        form = BasePlantLabelForm(instance=nfctag)

    return render(request, "domain/edit.html", {"form": form, "nfctag_uuid": nfctag_uuid})


@login_required
@never_cache
def register_nfctag(request, nfctag_uuid):
    nfctag = get_object_or_404(NFCTag, uuid=nfctag_uuid)
    try:
        service = NFCTagService(user=request.user)
        service.register_user(tag=nfctag)
        messages.success(request, _('NFC Tag successfully added to your account.'))
    except Exception:
        messages.error(request, _('This tag is already registered.'))
    return redirect(reverse('domain:list_nfctags'))


@login_required
@never_cache
def disconnect_nfctag(request, nfctag_uuid):
    nfctag = get_object_or_404(get_nfctags_for(fetched_by=request.user), uuid=nfctag_uuid)

    try:
        service = NFCTagService(user=request.user)
        service.disconnect_tag(nfctag)
        messages.success(request, _('NFC Tag successfully disconnected from your account.'))
    except Exception:
        messages.error(request, _('Failed to disconnect NFC Tag. It may not be registered to your account.'))
    return redirect(reverse('domain:list_nfctags'))
