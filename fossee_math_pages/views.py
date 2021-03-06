import json
import random
import re
import textwrap
import uuid
from itertools import chain

import pytz
import requests
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
# from django.contrib.sites.models import Site
from django.core.mail import send_mail, EmailMessage
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.timezone import now
from email_validator import validate_email, EmailNotValidError

from FOSSEE_math.email_config import SENDER_EMAIL
from .email_messages import (got_a_message, submission_status_changed, topic_assigned)
from .forms import (AddUserForm1, AddUserForm2, UserLoginForm, AddInternship, add_topic,
                    add_subtopic, data, imageFormatting, topicOrder,
                    subtopicOrder, addContributor, sendMessage, change_image, change_video,
                    EditUserForm1, EditUserForm2, EditBio, )
from .generic_functions import (large_img_size, large_video_size)
from .models import (UserDetails, Internship, Topic, Subtopic, Contributor, Data, ImageFormatting, HomeImages, Messages,
                     LogTable)
from .tokens import account_activation_token


# print(SENDER_EMAIL)


@login_required
def add_internship(request):
    if request.user.is_superuser:
        form = AddInternship()
        internship = Internship.objects.all()
        if request.method == 'POST':
            internship_topic = request.POST['internship_topic']
            form = AddInternship(request.POST, request.FILES)
            if Internship.objects.filter(internship_topic=internship_topic).exists():
                messages.error(request, 'That internship already exists!')
                return redirect('add-internship')
            if form.is_valid():
                obj = form.save(commit=False)
                obj.save()
                current_instance = Internship.objects.get(pk=obj.pk)
                current_instance.internship_url = '-'.join(str(internship_topic).lower().split())
                current_instance.save()
                messages.success(request, 'Internship added')
                return redirect('add-internship')
            else:
                messages.error(request, 'An error occured! Contact the admin!')  # What is this for?
                return redirect('add-internship')
        form = AddInternship()
        context = {
            'form': form,
            'internship': internship,
        }
        return render(request, 'fossee_math_pages/add-internship.html', context)
    else:
        return redirect('dashboard')


@login_required
def manage_internship(request):
    if request.user.is_superuser:
        internship = None

        if request.method == 'POST':
            if "search_internship" in request.POST:
                internship = Internship.objects.get(pk=request.POST['search_internship'])
            else:
                int_id = request.POST["id"]
                status = request.POST["status_change"]
                obj = get_object_or_404(Internship, id=int_id)
                if obj:
                    obj.internship_status = status
                    # obj.internship_completed_date = datetime.now()
                    obj.save()
                    messages.success(request, "Changed")
                    return redirect('manage-internship')
                else:
                    messages.error(request, "Error")
                    return redirect('manage-internship')

        internship_all = Internship.objects.all()

        context = {
            'internship': internship,
            'internship_all': internship_all,
        }
        return render(request, 'fossee_math_pages/manage-internship.html', context)
    else:
        return redirect('dashboard')


@login_required
def add_users(request):
    if request.user.is_superuser:
        datas = UserDetails.objects.all()
        user_contains_query = request.GET.get('title_contains')
        if user_contains_query != '' and user_contains_query is not None:
            datas = UserDetails.objects.filter(user_id__first_name__icontains=user_contains_query)
        if user_contains_query in ('STAFF', 'staff'):
            datas = UserDetails.objects.filter(user_role="STAFF")
        if user_contains_query in ('INTERN', 'intern'):
            datas = UserDetails.objects.filter(user_role="INTERN")

        form = AddUserForm1()
        sub_form = AddUserForm2()
        if request.method == 'POST':
            # register user
            firstname = request.POST['first_name']
            lastname = request.POST['last_name']
            email = request.POST['email']
            user_role = request.POST['user_role']
            user_phone = request.POST['user_phone']
            user_college = request.POST['user_college']
            user_status = 'INACTIVE'

            regex = re.compile(r'[@_!#$%^&*()<>?/\|}{~:]')
            if User.objects.filter(email=email).exists():
                messages.error(request, 'The email already exists')
                return redirect('add-users')
            if User.objects.filter(username=email).exists():
                messages.error(request, 'That username is being used')
                return redirect('add-users')
            if firstname.isdigit():
                messages.error(request, 'Firstname cannot have numbers')
                return redirect('add-users')
            if regex.search(firstname):
                messages.error(request, 'Firstname cannot have special characters')
                return redirect('add-users')
            if lastname.isdigit():
                messages.error(request, 'Lastname cannot have numbers')
                return redirect('add-users')
            if regex.search(lastname):
                messages.error(request, 'Lastname cannot have special characters')
                return redirect('add-users')
            Pattern = re.compile(r"(/+91)?[7-9][0-9]{9}")
            if Pattern.match(user_phone):
                messages.error(request, 'Phone number error')
                return redirect('add-users')
            try:
                v = validate_email(email)
                val_email = v["email"]
            except EmailNotValidError as e:
                messages.error(request, 'Invalid Email ID')
                return redirect('add-users')

            try:
                password = str(uuid.uuid1())[:16]
                user = User.objects.create_user(username=email, email=email, password=password, first_name=firstname,
                                                last_name=lastname, is_active=False)
                if user_role == 'STAFF' or user_role == 'MENTOR':
                    user.is_staff = True

                user.save()
            except Exception:
                messages.error(request, 'error in creating the User with the given details')
                return redirect('add-users')

            try:
                u_id = User.objects.get(username=email)

                addusr = UserDetails(user_id=u_id, user_phone=user_phone, user_role=user_role,
                                     user_temp_password=password, user_status=user_status, user_email=email,
                                     user_college=user_college)
                addusr.save()
            except Exception:
                u_id = User.objects.get(username=email)
                u_id.delete()
                messages.error(request, 'error in creating user with the other details')
                return redirect('add-users')

            current_site = get_current_site(request)
            mail_subject = "[Activate Account] FOSSEE Animations Mathematics"
            message = render_to_string('fossee_math_pages/activate_user.html', {
                'user': email,
                'firstname': firstname,
                'lastname': lastname,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
                'pass': password,
            })
            email = EmailMessage(mail_subject, message, from_email=SENDER_EMAIL, to=[email])
            email.send()

            messages.success(request, 'User Added!')
            return redirect('add-users')

        paginator = Paginator(datas, 25)  # Show 25 contacts per page.
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context = {
            'datas': page_obj,
            'form': form,
            'sub_form': sub_form,
        }
        return render(request, 'fossee_math_pages/add-users.html', context)
    else:
        return redirect('dashboard')


@login_required
def dashboard(request):
    if not request.user.is_superuser:
        user_details = UserDetails.objects.get(user_id=request.user.id)
    else:
        user_details = None

    context = {
        'l_active': 'nav_active',
        'user_details': user_details,
    }
    return render(request, 'fossee_math_pages/dashboard.html', context)


def contents(request, internship):
    internship_details = Internship.objects.get(internship_url=internship)
    id = internship_details.pk
    details = Internship.objects.get(id=id)
    topics = Topic.objects.filter(internship_id_id=id).order_by('topic_order')
    subtopics = Subtopic.objects.all().order_by('subtopic_order')

    if request.POST:
        search_contains_query = request.POST.get('title_contains')
        return home_search_results(request, search_contains_query)

    context = {
        'details': details,
        'topics': topics,
        'subtopics': subtopics,
    }
    return render(request, 'fossee_math_pages/contents.html', context)


def home_details(request, internship, topic, subtopic):
    selected_internship = Internship.objects.get(internship_url=internship)
    subtopic_request = Subtopic.objects.filter(topic_id__internship_id_id=selected_internship.pk).filter(
        topic_id__topic_url=topic).get(
        subtopic_url=subtopic)
    #print(subtopic)
    id = subtopic_request.pk
    subtopic_details = Subtopic.objects.get(id=id)
    contributor = ""
    ver = ""
    try:
        data = Data.objects.all().order_by('data_order')
        #print(data)
        imagesize = ImageFormatting.objects.all()
    except Data.DoesNotExist:
        data = None
        imagesize = None

    try:
        contributor = Contributor.objects.get(subtopic_id=subtopic_details.pk)
    except:
        contributor = None

    context = {
        'subtopic': subtopic_details,
        'datas': data,
        'contributor': contributor,
        'ver': ver,
        'imagesize': imagesize,
    }
    return render(request, 'fossee_math_pages/home_details.html', context)


def index(request):
    search_contains_query = request.GET.get('title_contains')
    images = HomeImages.objects.all()  # change

    interships = Internship.objects.filter(internship_status='COMPLETED')

    if search_contains_query != '' and search_contains_query is not None:
        return home_search_results(request, search_contains_query)

    context = {
        'internship': interships,
        'images': images,
        'home_active': 'nav_active',
    }

    return render(request, 'fossee_math_pages/index.html', context)


def home_search_results(request, search_contains_query):
    topic = Subtopic.objects.all()

    search_subtopic_name = Subtopic.objects.filter(subtopic_name__icontains=search_contains_query,
                                                   topic_id__internship_id__internship_status='COMPLETED')
    search_topic_name = Subtopic.objects.filter(topic_id__topic_name__icontains=search_contains_query,
                                                topic_id__internship_id__internship_status='COMPLETED')
    search_internship_name = Subtopic.objects.filter(
        topic_id__internship_id__internship_topic__icontains=search_contains_query,
        topic_id__internship_id__internship_status='COMPLETED')
    search_data_content = Subtopic.objects.filter(data__data_content__icontains=search_contains_query,
                                                  topic_id__internship_id__internship_status='COMPLETED')

    search_result = list(chain(search_subtopic_name, search_topic_name, search_internship_name, search_data_content))

    data_search = Data.objects.all()

    context = {
        'datas': search_result,
        'topic': topic,
        'querry': search_contains_query,
        'data_search': data_search,
    }
    return render(request, 'fossee_math_pages/home_search_results.html', context)


@login_required
def add_submission_subtopic(request, st_id):
    if request.user.is_authenticated and not request.user.is_staff and not request.user.is_superuser:
        form = data

        try:
            subtopic = Subtopic.objects.get(subtopic_hash=st_id)
        except Exception:
            messages.error(request, 'This subtopic does not exist!')
            return redirect('dashboard')

        t_id = subtopic.pk
        if subtopic.assigned_user_id_id == request.user.id:
            if request.method == 'POST':
                if subtopic.subtopic_status == "ACCEPTED":
                    return HttpResponse(status=403)
                content = request.POST.get('data_content')
                img = request.FILES.get('image')
                video = request.FILES.get('video')
                caption_image = request.POST.get('caption_image')
                caption_video = request.POST.get('caption_video')
                caption = None

                # checking for empty string for 'content'
                clean = re.compile('<.*?>')
                cleaned_data = re.sub(clean, '', content)
                cleaned_data = cleaned_data.replace("&nbsp;", " ")

                if img is None and video is None:
                    if cleaned_data.strip() == '':
                        messages.error(request, "Fill any one of the fields.")
                        return redirect('add-submission-subtopic', st_id)

                if img is None and cleaned_data.strip() == '':
                    caption = caption_video
                    video_file = str(video)
                    if not video_file.lower().endswith(('.mp4', '.webm')):
                        messages.error(request, 'Invalid File Type for Video')
                        return redirect('add-submission-subtopic', st_id)
                    if large_video_size(video):
                        messages.error(request, 'Maximum allowed size for Video is 30MB')
                        return redirect('add-submission-subtopic', st_id)

                if video is None and cleaned_data.strip() == '':
                    caption = caption_image
                    image = str(img)
                    if not image.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        messages.error(request, 'Invalid File Type for Image')
                        return redirect('add-submission-subtopic', st_id)
                    if large_img_size(img):
                        messages.error(request, 'Maximum Allowed Size for Image is 2MB')
                        return redirect('add-submission-subtopic', st_id)

                if caption:
                    if caption.strip() == '':
                        caption = None

                obj = Data.objects.filter(subtopic_id_id=t_id).order_by('data_order').last()
                if obj:
                    order = obj.data_order
                else:
                    order = 0

                order = order + 1
                add_data = Data(data_content=content, data_image=img,
                                data_video=video, data_caption=caption, subtopic_id_id=t_id, data_order=order)
                add_data.data_modification_date = now()
                add_data.save()
                sub = Subtopic.objects.get(pk=t_id)
                sub.subtopic_modification_date = now()
                sub.save()
                uuid_hash = uuid.uuid4()
                add_data.data_hash = str(uuid_hash)
                add_data.save()

                if img != "" or img != " ":
                    imgformat = ImageFormatting(data_id_id=add_data.pk, image_width='50%', image_height='50%')
                    imgformat.save()

            e_data = Data.objects.filter(subtopic_id=t_id).order_by('data_order')
            imagesize = ImageFormatting.objects.all()
            subtopic = Subtopic.objects.get(id=t_id)

            try:
                last_modified_UTC = sorted([dta.data_modification_date for dta in e_data])[-1]
                tz = pytz.timezone("Asia/Kolkata")
                last_modified_IST = last_modified_UTC.astimezone(tz)
                last_modified = last_modified_IST.strftime('%d %B, %Y %H:%M:%S (%A)')
            except IndexError:
                last_modified = "No modifications"

            context = {
                'topic': e_data,
                'form': form,
                'subtopic': subtopic,
                'imagesize': imagesize,
                'last_modified': last_modified,
            }

            return render(request, 'fossee_math_pages/add-submission-subtopic.html', context)
        else:
            messages.error(request, 'You do not have access to that subtopic submission!')
            return redirect('dashboard')
    else:
        return redirect('dashboard')


@login_required
def edit_text(request, t_id, id):
    if request.user.is_authenticated and not request.user.is_superuser and request.user.is_staff:
        instance = Data.objects.get(data_hash=id)
        subtopic = Subtopic.objects.get(id=instance.subtopic_id.pk)
        t_id = instance.subtopic_id.subtopic_hash
        if (subtopic.assigned_user_id.id == request.user.id) or request.user.is_staff:
            form = data(request.POST or None, instance=instance)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.save()
                if request.user.is_staff:
                    return redirect('review-submissions-subtopic', t_id)
                else:
                    return redirect('add-submission-subtopic', t_id)
        else:
            return redirect('dashboard')

        context = {
            'form': form,
            'subtopic': subtopic,
        }

        return render(request, 'fossee_math_pages/edit-text.html', context)
    else:
        return redirect('dashboard')


@login_required
def edit_media(request, t_id, id):
    if request.user.is_authenticated or request.user.is_staff: #and not request.user.is_superuser:
        instance = Data.objects.get(data_hash=id)
        subtopic = Subtopic.objects.get(id=instance.subtopic_id.pk)
        if (request.user.id == subtopic.assigned_user_id_id and subtopic.subtopic_status != 'ACCEPTED') or request.user.is_staff :
            form_text = data()
            form_image = change_image()
            from_video = change_video()
            current_image, caption_image, current_video, caption_video = "", "", "", ""
            t_id = instance.subtopic_id.subtopic_hash
            if request.POST:
                if "data_content" in request.POST:
                    content = request.POST.get('data_content')

                    # checking for empty string for 'content'
                    clean = re.compile('<.*?>')
                    cleaned_data = re.sub(clean, '', content)
                    cleaned_data = cleaned_data.replace("&nbsp;", " ")

                    if cleaned_data.strip() == '':
                        messages.error(request, "Fill any one of the field")
                        return redirect('edit-media', t_id, id)
                    else:
                        instance.data_content = content
                        instance.data_image = ""
                        instance.data_video = ""
                        instance.data_caption = ""
                        instance.data_modification_date = now()
                        instance.save()
                        sub = Subtopic.objects.get(pk=instance.subtopic_id.pk)
                        sub.subtopic_modification_date = now()
                        sub.save()
                        messages.success(request, 'Submission Updated Successfully')
                        return redirect('add-submission-subtopic', t_id)
                elif form_image:
                    img = request.FILES.get('data_image')
                    video = request.FILES.get('data_video')
                    caption = request.POST.get('data_caption')
                    if img is not None:
                        image = str(img)
                        if not image.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            messages.error(request, 'Inavalid File Type for Image')
                            return redirect('edit-media', t_id, id)
                        elif large_img_size(img):
                            messages.error(request, 'Maximum Allowed Size for Image is 2MB')
                            return redirect('edit-media', t_id, id)
                        else:
                            video = None
                    elif video is not None:
                        video_file = str(video)
                        if not video_file.lower().endswith(('.mp4', '.webm')):
                            messages.error(request, 'Inavalid File Type for Video')
                            return redirect('edit-media', t_id, id)
                        elif large_video_size(video):
                            messages.error(request, 'Maximum allowed size for Video is 30MB')
                            return redirect('edit-media', t_id, id)
                        else:
                            img = None
                    elif video is None and img is None:
                        messages.error(request, 'No Files selected to upload !')
                        return redirect('edit-media', t_id, id)
                    instance.data_content = ""
                    instance.data_image = img
                    instance.data_video = video
                    instance.data_caption = caption
                    instance.data_modification_date = now()
                    instance.save()
                    sub = Subtopic.objects.get(pk=instance.subtopic_id.pk)
                    sub.subtopic_modification_date = now()
                    sub.save()
                    messages.success(request, 'Image added Successfully !')
                    return redirect('add-submission-subtopic', t_id)
                elif from_video:
                    video = request.FILES.get('data_video')
                    img = request.FILES.get('data_image')
                    caption = request.POST.get('data_caption')
                    if img is not None:
                        image = str(img)
                        if not image.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            messages.error(request, 'Inavalid File Type for Image')
                            return redirect('edit-media', t_id, id)
                        elif large_img_size(img):
                            messages.error(request, 'Maximum Allowed Size for Image is 2MB')
                            return redirect('edit-media', t_id, id)
                        else:
                            video = None
                    elif video is not None:
                        video_file = str(video)
                        if not video_file.lower().endswith(('.mp4', '.webm')):
                            messages.error(request, 'Inavalid File Type for Video')
                            return redirect('edit-media', t_id, id)
                        elif large_video_size(video):
                            messages.error(request, 'Maximum allowed size for Video is 30MB')
                            return redirect('edit-media', t_id, id)
                        else:
                            img = None
                    elif video is None and img is None:
                        messages.error(request, 'No Files selected to upload !')
                        return redirect('edit-media', t_id, id)
                    instance.data_content = ""
                    instance.data_image = ""
                    instance.data_video = video
                    instance.data_caption = caption
                    instance.data_modification_date = now()
                    instance.save()
                    sub = Subtopic.objects.get(pk=instance.subtopic_id.pk)
                    sub.subtopic_modification_date = now()
                    sub.save()
                    messages.success(request, 'Video added Successfully !')
                    return redirect('add-submission-subtopic', t_id)
                else:
                    return redirect('add-submission-subtopic', t_id)
            else:
                if instance.data_content:
                    form_text = data(request.POST or None, instance=instance)
                elif instance.data_image:
                    current_image = instance.data_image
                    caption_image = instance.data_caption
                    form_image = change_image(request.POST, request.FILES, instance=instance)
                else:
                    current_video = instance.data_video
                    caption_image = instance.data_caption
                    from_video = change_video(request.POST, request.FILES, instance=instance)
            context = {
                'form_text': form_text,
                'form_image': form_image,
                'form_video': from_video,
                'subtopic': subtopic,
                'current_image': current_image,
                'caption_image': caption_image,
                'current_video': current_video,
                'caption_video': caption_video,
            }
            return render(request, 'fossee_math_pages/edit-media.html', context)
        else:
            messages.error(request, 'You no longer have access to that page!')
            return redirect('dashboard')
    else:
        return redirect('dashboard')


@login_required
def edit_image(request, t_id, id):
    if request.user.is_authenticated and not request.user.is_superuser:
        image = Data.objects.get(data_hash=id)
        try:
            image_size = ImageFormatting.objects.get(data_id_id=image.pk)
            form = imageFormatting(instance=image_size)
        except:
            image_size = None
            form = imageFormatting()
        if image.subtopic_id.subtopic_status != 'ACCEPTED' or request.user.is_staff:
            if request.POST:
                image_height = request.POST.get('image_height')
                image_width = request.POST.get('image_width')

                if re.match(r"\d+px$", image_height):
                    temp = re.findall(r'\d+', image_height)
                    res = list(map(int, temp))
                    if res[0] >= 500:
                        image_height = "500px"
                elif re.match(r"\d+%$", image_height):
                    temp = re.findall(r'\d+', image_height)
                    res = list(map(int, temp))
                    if res[0] >= 100:
                        image_height = "100%"
                else:
                    image_height = "500px"

                if re.match(r"\d+px$", image_width):
                    temp = re.findall(r'\d+', image_width)
                    res = list(map(int, temp))
                    if res[0] >= 900:
                        image_width = "900px"
                elif re.match(r"\d+%$", image_width):
                    temp = re.findall(r'\d+', image_width)
                    res = list(map(int, temp))
                    if res[0] >= 100:
                        image_width = "100%"
                else:
                    image_width = "500px"

                obj = ImageFormatting.objects.get(data_id_id=image.pk)
                obj.image_height = image_height
                obj.image_width = image_width
                obj.save()
                if request.user.is_staff:
                    return redirect('edit-image-staff', t_id, id)
                else:
                    return redirect('edit-image', t_id, id)

        context = {
            'image': image,
            'image_size': image_size,
            'form': form,
        }

        return render(request, 'fossee_math_pages/edit-image.html', context)
    else:
        return redirect('dashboard')


@login_required
def moveUpData(request, id):
    if request.user.is_authenticated and not request.user.is_superuser:
        instance = Data.objects.get(data_hash=id)
        if instance.subtopic_id.assigned_user_id.id == request.user.id and instance.subtopic_id.subtopic_status != 'ACCEPTED':
            t_id = instance.subtopic_id.subtopic_hash
            instance.data_order = instance.data_order - 1
            instance.save()
            try:
                current_order = Data.objects.filter(subtopic_id=instance.subtopic_id,
                                                    data_order=instance.data_order).exclude(pk=instance.pk).first()
                current_order.data_order = current_order.data_order + 1
                current_order.save()
            except:
                instance.data_order = instance.data_order + 1
                instance.save()
            return redirect('add-submission-subtopic', t_id)
        elif request.user.is_staff:
            t_id = instance.subtopic_id.subtopic_hash
            instance.data_order = instance.data_order - 1
            instance.save()
            try:
                current_order = Data.objects.filter(subtopic_id=instance.subtopic_id,
                                                    data_order=instance.data_order).exclude(pk=instance.pk).first()
                current_order.data_order = current_order.data_order + 1
                current_order.save()
            except:
                instance.data_order = instance.data_order + 1
                instance.save()
            return redirect('review-submissions-subtopic', t_id)
        else:
            return redirect('dashboard')
    else:
        return redirect('dashboard')

@login_required
def moveDownData(request, id):
    if request.user.is_authenticated and not request.user.is_superuser:
        instance = Data.objects.get(data_hash=id)
        if instance.subtopic_id.assigned_user_id.id == request.user.id and instance.subtopic_id.subtopic_status != 'ACCEPTED':
            t_id = instance.subtopic_id.subtopic_hash
            instance.data_order = instance.data_order + 1
            instance.save()
            try:
                current_order = Data.objects.filter(subtopic_id=instance.subtopic_id,
                                                    data_order=instance.data_order).exclude(pk=instance.pk).first()
                current_order.data_order = current_order.data_order - 1
                current_order.save()
            except:
                instance.data_order = instance.data_order - 1
                instance.save()
            return redirect('add-submission-subtopic', t_id)
        elif request.user.is_staff:
            t_id = instance.subtopic_id.subtopic_hash
            instance.data_order = instance.data_order + 1
            instance.save()
            try:
                current_order = Data.objects.filter(subtopic_id=instance.subtopic_id,
                                                    data_order=instance.data_order).exclude(pk=instance.pk).first()
                current_order.data_order = current_order.data_order - 1
                current_order.save()
            except:
                instance.data_order = instance.data_order + 1
                instance.save()
            return redirect('review-submissions-subtopic', t_id)
        else:
            return redirect('dashboard')
    else:
        return redirect('dashboard')


@login_required
def delete_data(request, id):
    if request.user.is_authenticated and not request.user.is_superuser:
        instance = Data.objects.get(data_hash=id)
        if instance.subtopic_id.assigned_user_id.id == request.user.id and instance.subtopic_id.subtopic_status != 'ACCEPTED':
            t_id = instance.subtopic_id.subtopic_hash
            try:
                image = ImageFormatting.objects.get(data_id=instance.id)
                image.delete()
                instance.delete()
            except:
                instance.delete()
            return redirect('add-submission-subtopic', t_id)

        elif request.user.is_staff:
            t_id = instance.subtopic_id.subtopic_hash
            try:
                image = ImageFormatting.objects.get(data_id=instance.id)
                image.delete()
                instance.delete()
            except:
                instance.delete()
            return redirect('review-submissions-subtopic', t_id)

        else:
            return redirect('dashboard')

    else:
        return redirect('dashboard')


@login_required
def add_submission(request):
    if request.user.is_authenticated and not request.user.is_staff and not request.user.is_superuser:
        assigned_topic = Subtopic.objects.filter(assigned_user_id_id=request.user.id)
        message = Messages.objects.filter(subtopic_id__assigned_user_id_id=request.user.id).last()
        context = {
            'assigned_topic': assigned_topic,
            'message': message,
        }
        if not assigned_topic is True:
            comic = random.randint(1, 2299)
            json_data = json.loads(requests.get("https://xkcd.com/{}/info.0.json".format(comic)).text)
            context["xkcd_img_url"] = json_data['img']
            context['xkcd_img_num'] = json_data['num']
        return render(request, 'fossee_math_pages/add-submission.html', context)
    else:
        return redirect('dashboard')


def internship(request):
    subtopic = Subtopic.objects.all()
    topic = Topic.objects.all()
    internship = Internship.objects.all()
    context = {
        'subtopic': subtopic,
        'topic': topic,
        'internship': internship,
        'i_active': 'nav_active',
    }

    return render(request, 'fossee_math_pages/internship.html', context)


def password_change(request):
    form = PasswordChangeForm(user=request.user)
    try:
        if request.method == 'POST':
            form = PasswordChangeForm(user=request.user, data=request.POST)
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, form.user)
                messages.success(request, 'Password Changed Successfully!')
                return redirect(dashboard)
    except NotImplementedError:
        messages.error(request, 'User is not logged in to change password !')

    context = {
        'form': form,
    }
    return render(request, "fossee_math_pages/password-change.html", context)


def user_login(request):
    user = None
    user = request.user
    if request.method == "POST":
        form = UserLoginForm(request.POST)
        if form.is_valid():
            try:
                user = form.authenticate_user()
                login(request, user)
                if request.user.is_staff:
                    log = LogTable(action='STAFF Loging in : ' + str(request.user), type='Successful',
                                   user_id=request.user)
                    log.save()
                    return redirect(dashboard)
                else:
                    user = UserDetails.objects.get(user_id=request.user.id)
                    if user.user_status == 'INACTIVE':
                        messages.error(request, "Your login credentials are invalid! Please contact the admin")
                        log = LogTable(action='User Loging in : ' + str(request.user) + ": INTERN status is inactive",
                                       type='UnSuccessful',
                                       user_id=request.user)
                        log.save()
                        logout(request)
                        form = UserLoginForm()
                        context = {
                            'form': form,
                        }
                        return render(request, "fossee_math_pages/login.html", context)
                    else:
                        log = LogTable(action='User Loging in : ' + str(request.user), type='Successful',
                                       user_id=request.user)
                        log.save()
                        return redirect(dashboard)
            except:
                form = UserLoginForm()
                context = {
                    'form': form,
                }
                messages.error(request, "Invalid Email or Password")
                return render(request, "fossee_math_pages/login.html", context)
        else:
            return render(request, "fossee_math_pages/login.html", {"form": form})
    else:
        form = UserLoginForm()
        return render(request, "fossee_math_pages/login.html", {"form": form, "l_active": 'nav_active'})


@login_required
def add_subtopics(request, i_id, t_id):
    if request.user.is_staff:
        form = add_subtopic()
        rearrange_subtopic = subtopicOrder()
        i_topic = Topic.objects.get(topic_url=t_id, internship_id__internship_url=i_id)
        subtopics = Subtopic.objects.all().order_by('subtopic_order')

        if request.method == 'POST':
            if "subtopic_order" in request.POST:
                subtopicoder = request.POST['subtopic_order']
                subtopic_id = request.POST['subtopicid']
                obj = Subtopic.objects.get(pk=subtopic_id)
                obj.subtopic_order = subtopicoder
                obj.save()
            elif "deletesubtopictopic" in request.POST:
                subtopic_id = request.POST['subtopic']
                topic_id = request.POST['deletesubtopictopic']
                subtopic = Subtopic.objects.get(subtopic_hash=subtopic_id)
                if Data.objects.filter(subtopic_id__topic_id_id=topic_id,
                                       subtopic_id__subtopic_hash=subtopic_id).exists():
                    messages.error(request, "Data exists for this subtopic, cannot delete!!")
                else:
                    subtopic.delete()
                    messages.success(request, "Subtopic deleted!")
            else:
                subtopic = request.POST['subtopic']
                topic_id = request.POST['id']

                if subtopic.strip() == '':
                    messages.error(request, "Fill the field")  # What is this?
                    return redirect('add-subtopics', t_id)
                else:
                    obj = Subtopic.objects.filter(topic_id__topic_url=t_id,
                                                  topic_id__internship_id_id=i_topic.internship_id).order_by(
                        'subtopic_order').last()
                    if obj:
                        order = obj.subtopic_order
                    else:
                        order = 0
                    try:
                        Subtopic.objects.get(subtopic_name=subtopic, topic_id_id=topic_id)
                        messages.error(request, "This subtopic already exists!")
                    except:
                        order = order + 1
                        data = Subtopic(subtopic_name=subtopic, topic_id_id=topic_id, subtopic_order=order)
                        data.save()
                        current_subtopic = Subtopic.objects.get(subtopic_name=subtopic, topic_id_id=topic_id)
                        # hashtext = str(current_subtopic.pk) + '-' + str(request.user.pk)
                        # hash_result = hashlib.md5(hashtext.encode())
                        current_subtopic.subtopic_hash = str(uuid.uuid1())  # hash_result.hexdigest()
                        current_subtopic.subtopic_url = '-'.join(str(subtopic).lower().split())
                        current_subtopic.save()
                        messages.success(request, 'Topic added with subtopic')  # What is this for?
                        i_topic = Topic.objects.get(topic_url=t_id, internship_id__internship_url=i_id)

        context = {
            'form': form,
            'i_topic': i_topic,
            'subtopics': subtopics,
            'rearrange_subtopic': rearrange_subtopic,
        }
        return render(request, 'fossee_math_pages/add-subtopics.html', context)
    else:
        return redirect('dashboard')


@login_required
def add_topics(request):
    if request.user.is_staff:
        form = add_topic()
        topic_order = topicOrder()
        internship = Internship.objects.filter(internship_status='ACTIVE').first()  # taking first active internship

        if request.method == 'POST':
            if "search_internship" in request.POST:
                internship = Internship.objects.get(pk=request.POST['search_internship'])
            elif "topic_order" in request.POST:
                topoder = request.POST['topic_order']
                topic_id = request.POST['topicid']
                obj = Topic.objects.get(pk=topic_id)
                obj.topic_order = topoder
                obj.save()
            elif "deletetopic" in request.POST:
                topic_id = request.POST['deletetopic']
                internship_id = request.POST['internshipid']

                subtopic = Subtopic.objects.filter(topic_id=topic_id)
                if subtopic:
                    messages.error(request, "Subtopics exist for this topic; cannot delete!")
                    internship = Internship.objects.get(pk=internship_id)
                else:
                    topic = Topic.objects.get(pk=topic_id)
                    topic.delete()
                    messages.success(request, "Topic deleted!")
                    internship = Internship.objects.get(pk=internship_id)
            else:
                topic = request.POST['topic']
                id = request.POST['id']
                if topic.strip() == '':
                    messages.error(request, "Fill in the topic name")
                    return redirect(add_topics)
                else:
                    obj = Topic.objects.filter(internship_id_id=id).order_by('topic_order').last()
                    if obj:
                        order = obj.topic_order
                    else:
                        order = 0
                    try:
                        Topic.objects.get(topic_name=topic, internship_id_id=id)
                        messages.error(request, "This Topic alredy exists!")
                    except:
                        order = order + 1
                        data = Topic(topic_name=topic, internship_id_id=id, topic_order=order)
                        data.save()
                        current_topic = Topic.objects.get(topic_name=topic, internship_id_id=id)
                        current_topic.topic_url = '-'.join(str(topic).lower().split())
                        current_topic.save()
                        messages.success(request, 'Topic added!')
                        internship = Internship.objects.get(pk=current_topic.internship_id.pk)

        internship_all = Internship.objects.all()
        topic = Topic.objects.all().order_by('topic_order')

        context = {
            'form': form,
            'internship': internship,
            'internship_all': internship_all,
            'topic': topic,
            'topic_order': topic_order,
        }
        return render(request, 'fossee_math_pages/add-topics.html', context)
    else:
        return redirect('dashboard')


@login_required
def review_submissions(request):
    if request.user.is_staff:
        selected_intern = ""
        first_internship = ""
        interns = User.objects.filter(userdetails__user_role='INTERN', userdetails__user_status='ACTIVE')
        internship = Internship.objects.all()
        user_query = request.GET.get('title_contains')
        if user_query != '' and user_query is not None:
            subtopic = Subtopic.objects.filter(subtopic_name__icontains=user_query)
        else:
            subtopic = Subtopic.objects.all().order_by('topic_id__internship_id').order_by(
                'topic_id__topic_order').order_by(
                'subtopic_order').order_by('-subtopic_modification_date')
        messages_user = Messages.objects.all()
        userdetails = UserDetails.objects.all()

        if "search_internship" in request.POST:
            subtopic = Subtopic.objects.filter(topic_id__internship_id_id=request.POST['search_internship']).order_by(
                'topic_id__topic_order').order_by('subtopic_order').order_by('-subtopic_modification_date')
            first_internship = Internship.objects.get(pk=request.POST['search_internship'])
            interns = User.objects.order_by('pk').filter(userdetails__user_role='INTERN').filter(
                userdetails__user_status='ACTIVE').filter(
                subtopic__topic_id__internship_id_id=request.POST['search_internship']).distinct

        if "search_intern" in request.POST:
            if request.POST['selected_internship'] != "":
                subtopic = Subtopic.objects.filter(
                    topic_id__internship_id_id=request.POST['selected_internship']).filter(
                    assigned_user_id=request.POST['search_intern']).order_by('subtopic_order').order_by(
                    '-subtopic_modification_date')
                first_internship = Internship.objects.get(pk=request.POST['selected_internship'])
                interns = User.objects.order_by('pk').filter(userdetails__user_role='INTERN').filter(
                    userdetails__user_status='ACTIVE').filter(
                    subtopic__topic_id__internship_id_id=request.POST['selected_internship']).distinct
                selected_intern = User.objects.get(pk=request.POST['search_intern'])
            else:
                messages.error(request, 'Select an Internship First')
                return redirect('review-submissions')

        context = {
            'subtopic': subtopic,
            'internship': internship,
            'first_internship': first_internship,
            'interns': interns,
            'userdetails': userdetails,
            'messages_user': messages_user,
            'selected_intern': selected_intern,
        }

        return render(request, 'fossee_math_pages/review-submissions.html', context)
    else:
        return redirect('dashboard')


# HERE
@login_required
def manage_interns(request):
    if request.user.is_staff and not request.user.is_superuser:
        subtopic = Subtopic.objects.all()
        interns = UserDetails.objects.filter(user_role='INTERN')

        search_query = request.GET.get('title_contains')
        if search_query is None or search_query == '.':
            interns = UserDetails.objects.filter(user_role='INTERN')
        else:
            interns = UserDetails.objects.filter(user_role='INTERN',
                                                 user_id__first_name__icontains=search_query)

        if request.method == 'POST':
            current_user = UserDetails.objects.get(user_id_id=request.POST['assigneduserid'])
            status = request.POST["status_change"]
            current_user.user_status = status
            current_user.save()
            messages.success(request, "Intern Status Changed")

        context = {
            'interns': interns,
            'subtopic': subtopic,
            'searchq': search_query,
        }
        return render(request, 'fossee_math_pages/manage-interns.html', context)

    elif request.user.is_superuser:
        interns = UserDetails.objects.filter(user_role="INTERN")

        search_query = request.GET.get('title_contains')
        if search_query is None or search_query == '.':
            interns = UserDetails.objects.filter(user_role='INTERN')
        else:
            interns = UserDetails.objects.filter(user_role='INTERN',
                                                 user_id__first_name__icontains=search_query)

        if request.method == 'POST':
            int_id = request.POST["id"]
            status = request.POST["status_change"]
            obj = UserDetails.objects.get(user_id_id=int_id)
            if obj:
                obj.user_status = status
                obj.save()
                messages.success(request, "Changed")
                return redirect('manage-interns')
            else:
                messages.error(request, "Error")
                return redirect('manage-interns')

        context = {
            'interns': interns,
        }
        return render(request, 'fossee_math_pages/manage-interns.html', context)
    else:
        return redirect('dashboard')


@login_required
def assign_topics(request):
    if request.user.is_staff and not request.user.is_superuser:
        internship = Internship.objects.all()
        interns = User.objects.filter(userdetails__user_role='INTERN', userdetails__user_status='ACTIVE')
        first_internsip = Internship.objects.filter(
            internship_status='ACTIVE').first()  # taking first active internship
        if first_internsip:
            subtopic = Subtopic.objects.all().order_by('topic_id__topic_order').filter(
                topic_id__internship_id_id=first_internsip.pk)

            if request.method == 'POST':
                if "search_internship" in request.POST:
                    first_internsip = Internship.objects.get(pk=request.POST['search_internship'])
                    try:
                        subtopic = Subtopic.objects.filter(topic_id__internship_id_id=first_internsip.pk)
                    except:
                        subtopic = None
                elif "deletetheassign" in request.POST:
                    s_id = request.POST['deletetheassign']
                    st = Subtopic.objects.get(subtopic_hash=s_id)
                    first_internsip = Internship.objects.get(pk=st.topic_id.internship_id.pk)
                    subtopic = Subtopic.objects.filter(topic_id__internship_id_id=first_internsip.pk)
                    if st.subtopic_status == 'ACCEPTED':
                        messages.error(request, 'Subtopic has alredy been completed and Accepted!')
                    else:
                        st.assigned_user_id = None
                        st.save()
                else:
                    selectd_subtopic = Subtopic.objects.get(pk=request.POST["subtopicid"])
                    if request.POST["assigned_user_id"] != "":
                        user = User.objects.get(pk=request.POST["assigned_user_id"])
                        ud = UserDetails.objects.get(user_id_id=user.pk)
                        if ud.user_status == 'ACTIVE':
                            selectd_subtopic.assigned_user_id_id = user.id
                            selectd_subtopic.save()  # add email here
                            scheme = request.is_secure() and "https" or "http"
                            subtopic_link = "{}://{}/add-submission/{}".format(scheme, request.META['HTTP_HOST'],
                                                                               selectd_subtopic.subtopic_hash)
                            subject, email_message = topic_assigned(user.first_name, user.last_name,
                                                                    selectd_subtopic.topic_id.topic_name, subtopic_link)
                            send_mail(subject, email_message, SENDER_EMAIL, [user.email], fail_silently=True)
                            messages.success(request, 'Topic assigned to the intern')
                        else:
                            messages.error(request, 'User is Inactive. This action requires admin privileges!')
                    else:
                        messages.error(request, 'Select an Intern to Assign')
                    first_internsip = Internship.objects.get(pk=selectd_subtopic.topic_id.internship_id.pk)
                    subtopic = Subtopic.objects.filter(
                        topic_id__internship_id_id=selectd_subtopic.topic_id.internship_id.pk)

            context = {
                'interns': interns,
                'subtopic': subtopic,
                'intern': internship,
                'chosen_inernship': first_internsip,
            }
            return render(request, 'fossee_math_pages/assign-topics.html', context)
        else:
            messages.error(request, 'No active Internships !!')
            return redirect('dashboard')
    else:
        return redirect('dashboard')


@login_required
def interns(request):
    if request.user.is_staff:
        topics = Subtopic.objects.all()
        internship_all = Internship.objects.all()
        interns = UserDetails.objects.filter(user_role='INTERN')
        internship = Internship.objects.filter(internship_status='ACTIVE').first()  # taking first active internship
        if internship:
            internship = Internship.objects.get(pk=internship.pk)

            if "search_internship" in request.POST:
                internship = Internship.objects.get(pk=request.POST['search_internship'])

            conxext = {
                'topics': topics,
                'interns': interns,
                'internship': internship,
                'internship_all': internship_all,
            }
            return render(request, 'fossee_math_pages/interns.html', conxext)
        else:
            messages.error(request, "No active Internships !!")
            return redirect('dashboard')
    else:
        return redirect('dashboard')


@login_required
def internship_progress(request):
    if request.user.is_staff or request.user.is_superuser:
        internship = Internship.objects.filter(internship_status='ACTIVE').first()  # taking first active internship
        if internship:
            internship = Internship.objects.filter(pk=internship.pk)
            topics = Topic.objects.all()
            subtopics = Subtopic.objects.all()
            internship_all = Internship.objects.all()

            if "search_internship" in request.POST:
                internship = Internship.objects.filter(pk=request.POST['search_internship'])

            context = {
                'internship': internship,
                'topics': topics,
                'subtopics': subtopics,
                'internship_all': internship_all,
                'chosen_internship': internship[0],
            }
            return render(request, 'fossee_math_pages/internship-progress.html', context)
        else:
            messages.error(request, "No active Internships !!")
            return redirect('dashboard')

    elif request.user.is_authenticated and not request.user.is_staff and not request.user.is_superuser:
        internship = Internship.objects.all()
        subtopics = Subtopic.objects.all()

        context = {
            'internship': internship,
            'subtopics': subtopics,
        }
        return render(request, 'fossee_math_pages/internship-progress.html', context)

    else:
        return redirect('dashboard')


@login_required
def review_submissions_subtopic(request, s_id):
    if request.user.is_staff:
        subtopic = Subtopic.objects.get(subtopic_hash=s_id)
        imageformat = ImageFormatting.objects.all()
        user_staff = UserDetails.objects.filter(user_role='STAFF')

        if request.method == "POST":
            if "message" in request.POST:
                message = request.POST['message']
                obj = Messages(subtopic_id_id=subtopic.pk, user_id_id=request.user.pk, message=message,
                               message_send_date=now())
                obj.save()
                scheme = request.is_secure() and "https" or "http"
                message_link = "{}://{}/dashboard/messages/{}".format(scheme, request.META['HTTP_HOST'],
                                                                      subtopic.subtopic_hash)
                # print(message_link)
                username = request.user.first_name + " " + request.user.last_name
                subject, email_body = got_a_message(subtopic.assigned_user_id.first_name,
                                                    subtopic.assigned_user_id.last_name,
                                                    subtopic.subtopic_name, username, message,
                                                    message_link)
                send_mail(subject, email_body, SENDER_EMAIL, [subtopic.assigned_user_id.email], fail_silently=True)

            elif "mentor" in request.POST:
                mentor = request.POST['mentor']
                professor = request.POST['professor']

                try:
                    if mentor.strip() != '' and professor.strip() != "":
                        contributor = subtopic.assigned_user_id.first_name + " " + subtopic.assigned_user_id.last_name
                        obj = Contributor.objects.get(subtopic_id_id=subtopic.pk)
                        obj.contributor = contributor
                        obj.mentor = mentor
                        obj.professor = professor
                        obj.save()
                except:
                    contributor = subtopic.assigned_user_id.first_name + " " + subtopic.assigned_user_id.last_name
                    obj = Contributor(subtopic_id_id=subtopic.pk, contributor=contributor, mentor=mentor,
                                      professor=professor, data_aproval_date=now())
                    obj.save()
            else:
                content = request.POST.get('data_content')
                img = request.FILES.get('image')
                video = request.FILES.get('video')
                caption_image = request.POST.get('caption_image')
                caption_video = request.POST.get('caption_video')
                caption = None

                # checking for empty string for 'content'
                clean = re.compile('<.*?>')
                cleaned_data = re.sub(clean, '', content)
                cleaned_data = cleaned_data.replace("&nbsp;", " ")

                if img is None and video is None:
                    if cleaned_data.strip() == '':
                        messages.error(request, "Fill any one of the fields.")
                        return redirect('review-submissions-subtopic', s_id)

                if img is None and cleaned_data.strip() == '':
                    caption = caption_video
                    video_file = str(video)
                    if not video_file.lower().endswith(('.mp4', '.webm')):
                        messages.error(request, 'Invalid File Type for Video')
                        return redirect('review-submissions-subtopic', s_id)
                    if large_video_size(video):
                        messages.error(request, 'Maximum allowed size for Video is 30MB')
                        return redirect('review-submissions-subtopic', s_id)

                if video is None and cleaned_data.strip() == '':
                    caption = caption_image
                    image = str(img)
                    if not image.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        messages.error(request, 'Invalid File Type for Image')
                        return redirect('review-submissions-subtopic', s_id)
                    if large_img_size(img):
                        messages.error(request, 'Maximum Allowed Size for Image is 2MB')
                        return redirect('review-submissions-subtopic', s_id)

                if caption:
                    if caption.strip() == '':
                        caption = None

                obj = Data.objects.filter(subtopic_id_id=subtopic.pk).order_by('data_order').last()
                if obj:
                    order = obj.data_order
                else:
                    order = 0

                order = order + 1
                add_data = Data(data_content=content, data_image=img,
                                data_video=video, data_caption=caption, subtopic_id_id=subtopic.pk, data_order=order)
                add_data.data_modification_date = now()
                add_data.save()
                sub = Subtopic.objects.get(pk=subtopic.pk)
                sub.subtopic_modification_date = now()
                sub.save()
                uuid_hash = uuid.uuid4()
                add_data.data_hash = str(uuid_hash)
                add_data.save()

                if img != "" or img != " ":
                    imgformat = ImageFormatting(data_id_id=add_data.pk, image_width='50%', image_height='50%')
                    imgformat.save()

        data_results = Data.objects.filter(subtopic_id=subtopic.pk).order_by('data_order')
        form_message = sendMessage()
        form_data = data

        try:
            instance = Contributor.objects.get(subtopic_id_id=subtopic.pk)
            form = addContributor(request.POST or None, instance=instance)
        except Exception:
            form = addContributor()

        context = {
            'subtopic': subtopic,
            'datas': data_results,
            'form_data': form_data,
            'imagesize': imageformat,
            'form': form,
            'form_message': form_message,
            'user_staff': user_staff,
        }

        return render(request, 'fossee_math_pages/review-submissions-subtopic.html', context)
    else:
        return redirect('dashboard')


@login_required
def approve_subtopic(request, id):
    if request.user.is_staff:
        instance = Subtopic.objects.get(subtopic_hash=id)
        t_id = instance.pk
        print(instance, t_id)
        try:
            data = Data.objects.filter(subtopic_id_id=t_id)
            print(data)
        except Data.DoesNotExist:
            # print(data)
            data = None
        print(data)
        if data:
            instance.subtopic_status = "ACCEPTED"
            instance.subtopic_managed_user = request.user.pk
            instance.save()
            scheme = request.is_secure() and "https" or "http"
            message_link = "{}://{}/dashboard/messages/{}".format(scheme, request.META['HTTP_HOST'],
                                                                  instance.subtopic_hash)
            subtopic_link = "{}://{}/add-submission/{}".format(scheme, request.META['HTTP_HOST'],
                                                               instance.subtopic_hash)
            subject, email_message = submission_status_changed(instance.assigned_user_id.first_name,
                                                               instance.assigned_user_id.last_name,
                                                               instance.subtopic_name, instance.subtopic_status,
                                                               message_link, subtopic_link)
            send_mail(subject, email_message, SENDER_EMAIL, [instance.assigned_user_id.email], fail_silently=True)
            return redirect('review-submissions-subtopic', instance.subtopic_hash)
        else:
            messages.error(request, 'An empty submission cannot be Approved!')
            return redirect('review-submissions-subtopic', instance.subtopic_hash)
    else:
        return redirect('dashboard')


@login_required
def reject_subtopic(request, id):
    if request.user.is_staff:
        instance = Subtopic.objects.get(subtopic_hash=id)
        try:
            data = Data.objects.filter(subtopic_id_id=instance.id)
        except Data.DoesNotExist:
            data = None

        if data:
            t_id = instance.pk
            instance.subtopic_status = "REJECTED"
            instance.subtopic_managed_user = request.user.pk
            instance.save()
            scheme = request.is_secure() and "https" or "http"
            message_link = "{}://{}/dashboard/messages/{}".format(scheme, request.META['HTTP_HOST'],
                                                                  instance.subtopic_hash)
            subtopic_link = "{}://{}/add-submission/{}".format(scheme, request.META['HTTP_HOST'],
                                                               instance.subtopic_hash)
            subject, email_message = submission_status_changed(instance.assigned_user_id.first_name,
                                                               instance.assigned_user_id.last_name,
                                                               instance.subtopic_name, instance.subtopic_status,
                                                               message_link, subtopic_link)
            send_mail(subject, email_message, SENDER_EMAIL, [instance.assigned_user_id.email], fail_silently=True)
            return redirect('review-submissions-subtopic', instance.subtopic_hash)
        else:
            messages.error(request, 'An empty submission cannot be Rejected!')
            return redirect('review-submissions-subtopic', instance.subtopic_hash)
    else:
        return redirect('dashboard')


@login_required
def view_messages(request, s_id):
    if not request.user.is_staff and not request.user.is_superuser:
        message = Messages.objects.filter(subtopic_id__subtopic_hash=s_id)
        subtopic = Subtopic.objects.get(subtopic_hash=s_id)
        if request.user.id == subtopic.assigned_user_id_id:
            form = sendMessage()

            try:
                m = Messages.objects.filter(subtopic_id__subtopic_hash=s_id).order_by('subtopic_id').last()
                m.message_is_seen_intern = 1
                m.save()
            except:
                m = None

            if request.POST:
                mess = request.POST['message']
                wrap_text = textwrap.TextWrapper(width=80)
                wrap_list = wrap_text.wrap(text=mess)
                mess = "\n".join(wrap_list)
                # print(mess)
                save_mess = Messages(message=mess, message_send_date=now(), subtopic_id_id=subtopic.pk,
                                     user_id_id=request.user.pk)
                save_mess.message_is_seen_intern = 1
                save_mess.message_is_seen_staff = 0
                save_mess.save()

            context = {
                'message': message,
                'form': form,
                'subtopic': subtopic,
            }
            return render(request, 'fossee_math_pages/messages.html', context)
        else:
            messages.error(request, "Stop snooping around! Don't you have an assignment or something?")
            return redirect('dashboard')
    elif request.user.is_staff:
        message = Messages.objects.filter(subtopic_id__subtopic_hash=s_id)
        form = sendMessage()
        subtopic = Subtopic.objects.get(subtopic_hash=s_id)
        try:
            m = Messages.objects.filter(subtopic_id__subtopic_hash=s_id).order_by('subtopic_id').last()
            m.message_is_seen_staff = 1
            m.save()
        except:
            m = None
        if request.POST:
            mess = request.POST['message']
            save_mess = Messages(message=mess, message_send_date=now(), subtopic_id_id=subtopic.pk,
                                 user_id_id=request.user.pk)
            save_mess.message_is_seen_staff = 1
            save_mess.message_is_seen_intern = 0
            save_mess.save()
            scheme = request.is_secure() and "https" or "http"
            message_link = "{}://{}/dashboard/messages/{}".format(scheme, request.META['HTTP_HOST'],
                                                                  subtopic.subtopic_hash)
            # print(message_link)
            username = request.user.first_name + " " + request.user.last_name
            subject, email_body = got_a_message(subtopic.assigned_user_id.first_name,
                                                subtopic.assigned_user_id.last_name,
                                                subtopic.subtopic_name, username, mess, message_link)
            send_mail(subject, email_body, SENDER_EMAIL, [subtopic.assigned_user_id.email], fail_silently=True)

        context = {
            'message': message,
            'form': form,
            'subtopic': subtopic,
        }
        return render(request, 'fossee_math_pages/messages.html', context)
    else:
        return redirect('dashboard')


@login_required
def user_logout(request):
    log = LogTable(action='User Loging out : ' + str(request.user), type='Successful', user_id=request.user)
    log.save()
    logout(request)
    return redirect('index')


def error_404_view(request, exception):
    return render(request, 'fossee_math_pages/404.html')


def error_500_view(request):
    return render(request, 'fossee_math_pages/500.html')


def activate(request, uidb64, token):
    try:
        # uidb64 = uidb64.decode('utf-8')
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        userdetails = UserDetails.objects.get(user_id=user.pk)
        userdetails.user_status = 'ACTIVE'
        userdetails.save()
        return redirect('activate-account')
    else:
        messages.error(request, 'Activation link is invalid!')
        return redirect('login')


def password_set(request):
    form = PasswordChangeForm(user=request.user)
    try:
        if request.method == 'POST':
            form = PasswordChangeForm(user=request.user, data=request.POST)
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, form.user)
                messages.success(request, 'Password Changed Successfully!')
                return redirect(dashboard)
    except NotImplementedError:
        messages.error(request, 'User is not expected to visit this page again !')
    context = {
        'form': form,
    }
    return render(request, "password_reset/password_set.html", context)


def profile(request, id, username):
    userdetails = UserDetails.objects.get(user_id_id=id)
    if userdetails:
        name = userdetails.user_id.first_name + userdetails.user_id.last_name
        if name == username:
            if request.POST:
                bio = request.POST['user_bio']
                userdetails.user_bio = bio
                userdetails.save()

            if userdetails.user_role == 'INTERN':
                subtopic = Subtopic.objects.all()
                messages_send = None
            elif userdetails.user_role == 'STAFF':
                subtopic = Subtopic.objects.all()
                messages_send = Messages.objects.values('subtopic_id').distinct()
            else:
                subtopic = None
                messages_send = None

            print(messages_send)
            form_edit_bio = EditBio(instance=userdetails)
            scheme = request.is_secure() and "https" or "http"
            profile_url = "{}://{}/profile/{}/{}".format(scheme, request.META['HTTP_HOST'], userdetails.user_id.pk,
                                                         name)
        else:
            subtopic = None
            profile_url = None
            form_edit_bio = None
            userdetails = None
            messages_send = None
            messages.error(request, 'Invalid User !')

    else:
        subtopic = None
        profile_url = None
        form_edit_bio = None
        userdetails = None
        messages_send = None
        messages.error(request, 'Invalid User !')

    context = {
        'details': userdetails,
        'subtopic': subtopic,
        'messages_send': messages_send,
        'profile_url': profile_url,
        'form_edit_bio': form_edit_bio,
        'l_active': 'nav_active'
    }
    return render(request, 'fossee_math_pages/profile.html', context)


@login_required
def rearrange(request):
    if request.user.is_superuser:
        subtopic = Subtopic.objects.all().order_by('topic_id')
        user_query = request.GET.get('title_contains')
        if user_query != '' and user_query is not None:
            subtopic = Subtopic.objects.filter(subtopic_name__icontains=user_query)

        if request.POST:
            if "select_internship" in request.POST:
                new_internship = request.POST['select_internship']
                new_topic = request.POST['select_topic']
                new_subtopic = request.POST['select_subtopic']
                reassign_subtopic = Subtopic.objects.get(pk=new_subtopic)
                reassign_subtopic.topic_id_id = new_topic
                reassign_subtopic.topic_id.internship_id_id = new_internship
                reassign_subtopic.save()
                messages.success(request, "Subtopic changed !")

        if subtopic:
            internships = Internship.objects.all()
            topics = Topic.objects.all()
        else:
            messages.error(request, "No Subtopics !")
            return redirect('dashboard')

        if subtopic:
            paginator = Paginator(subtopic, 10)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)

        context = {
            'subtopic': page_obj,
            'internships': internships,
            'topics': topics,
        }
        return render(request, 'fossee_math_pages/rearrange_topics.html', context)
    else:
        messages.error(request, 'You dont have access to this pages !!')
        return redirect('dashboard')


@login_required
def update_profile(request, user_id):
    instance_user = User.objects.get(username__exact=user_id)
    if instance_user:
        instance_userdetails = UserDetails.objects.get(user_id=instance_user.id)
        form = EditUserForm1(instance=instance_user)
        sub_form = EditUserForm2(instance=instance_userdetails)

        if request.method == 'POST':
            firstname = request.POST['first_name']
            lastname = request.POST['last_name']
            email = request.POST['email']
            user_phone = request.POST['user_phone']
            user_college = request.POST['user_college']
            user_bio = request.POST['user_bio']

            regex = re.compile(r'[@_!#$%^&*()<>?/\|}{~:]')
            if firstname.isdigit():
                messages.error(request, 'Firstname cannot have numbers')
                return redirect('update-profile', user_id)
            if regex.search(firstname):
                messages.error(request, 'Firstname cannot have special characters')
                return redirect('update-profile', user_id)
            if lastname.isdigit():
                messages.error(request, 'Lastname cannot have numbers')
                return redirect('update-profile', user_id)
            if regex.search(lastname):
                messages.error(request, 'Lastname cannot have special characters')
                return redirect('update-profile', user_id)
            Pattern = re.compile(r"(/+91)?[7-9][0-9]{9}")
            if Pattern.match(user_phone):
                messages.error(request, 'Phone number error')
                return redirect('update-profile', user_id)
            try:
                v = validate_email(email)
                val_email = v["email"]
            except EmailNotValidError as e:
                messages.error(request, 'Invalid Email ID')
                return redirect('update-profile', user_id)

            try:
                user = User.objects.get(pk=instance_user.pk)
                user.username = email
                user.email = email
                user.first_name = firstname
                user.last_name = lastname
                user.save()
                addusr = UserDetails.objects.get(user_id=instance_user.id)
                addusr.user_phone = user_phone
                addusr.user_email = email
                addusr.user_college = user_college
                addusr.user_bio = user_bio
                addusr.save()
            except Exception:
                messages.error(request, 'error in updating the User with the given details')
                return redirect('add-users')

            messages.success(request, 'User Updated!')
            return redirect('add-users')

        context = {
            'form': form,
            'subform': sub_form,
            'currentuser': instance_user,
        }
        return render(request, 'fossee_math_pages/update-user.html', context)
    else:
        messages.error(request, 'Invalid User')
        return redirect('add-users')


@login_required
def reset_subtopic_status(request, id):
    if request.user.is_staff:
        instance = Subtopic.objects.get(subtopic_hash=id)
        try:
            data = Data.objects.filter(subtopic_id_id=instance.id)
        except Data.DoesNotExist:
            data = None

        if data:
            instance.subtopic_status = "WAITING"
            instance.save()
            scheme = request.is_secure() and "https" or "http"
            message_link = "{}://{}/dashboard/messages/{}".format(scheme, request.META['HTTP_HOST'],
                                                                  instance.subtopic_hash)
            subtopic_link = "{}://{}/add-submission/{}".format(scheme, request.META['HTTP_HOST'],
                                                               instance.subtopic_hash)
            subject, email_message = submission_status_changed(instance.assigned_user_id.first_name,
                                                               instance.assigned_user_id.last_name,
                                                               instance.subtopic_name, instance.subtopic_status,
                                                               message_link, subtopic_link)
            send_mail(subject, email_message, SENDER_EMAIL, [instance.assigned_user_id.email], fail_silently=True)
            return redirect('review-submissions-subtopic', instance.subtopic_hash)
        else:
            messages.error(request, 'An empty submission cannot be Rejected!')
            return redirect('review-submissions-subtopic', instance.subtopic_hash)
    else:
        return redirect('dashboard')


def edit_topics(request, id):
    internship = Internship.objects.get(internship_url=id)
    topics = Topic.objects.filter(internship_id=internship.id)
    subtopics = Subtopic.objects.filter(topic_id__internship_id=internship.id)

    if request.user.is_superuser:
        if request.POST:
            if "internship_topic_new" in request.POST:
                internship_topic_new = request.POST['internship_topic_new']
                internship_id = request.POST['internship_id']
                current_internship = Internship.objects.get(pk=internship_id)
                current_internship.internship_topic = internship_topic_new
                current_internship.internship_url = '-'.join(str(internship_topic_new).lower().split())
                current_internship.save()
                messages.success(request, 'Changed the Internship topic !')
                return redirect(edit_topics, current_internship.internship_url)
            elif "topic_new" in request.POST:
                topic_new = request.POST['topic_new']
                topic_id = request.POST['topic_id']
                current_topic = Topic.objects.get(pk=topic_id)
                current_topic.topic_name = topic_new
                current_topic.topic_url = '-'.join(str(topic_new).lower().split())
                current_topic.save()
                messages.success(request, 'Changed the Topic !')
                return redirect(edit_topics, id)
            elif "subtopic_new" in request.POST:
                subtopic_new = request.POST['subtopic_new']
                subtopic_id = request.POST['subtopic_id']
                current_subtopic = Subtopic.objects.get(pk=subtopic_id)
                current_subtopic.subtopic_name = subtopic_new
                current_subtopic.subtopic_url = '-'.join(str(subtopic_new).lower().split())
                current_subtopic.save()
                messages.success(request, 'Changed the Subtopic !')
                return redirect(edit_topics, id)

    else:
        messages.error(request, 'Inavalid access !')
        return redirect('dashboard')

    context = {
        'internship': internship,
        'topics': topics,
        'subtopics': subtopics,
    }
    return render(request, 'fossee_math_pages/edit-topics.html', context)


@login_required
def loadLogs(request):
    if request.user.is_superuser:
        log = LogTable(action='Accessing Log Tables', type='Successful', user_id=request.user)
        log.save()

        server_logs = LogTable.objects.all().order_by('-timeStamp')

        paginator = Paginator(server_logs, 25)  # Show 25 contacts per page.
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
        }
        return render(request, 'fossee_math_pages/load-logs.html', context)
    else:
        log = LogTable(action='Accessing Log Tables', type='Invalid Access', user_id=request.user)
        log.save()
        return redirect('dashboard')


@login_required
def add_mentor(request):
    if request.user.is_superuser:

        mentors = UserDetails.objects.filter(user_role='MENTOR')

        context = {
            'mentors': mentors
        }
        return render(request, 'fossee_math_pages/add-mentor.html', context)
    else:
        return redirect('dashboard')
