"""Views."""

from flask import render_template, request, redirect, url_for, flash, send_from_directory, Flask
from lxml import etree
import json
import requests
import re
import urllib.request
import zipfile
import os
import smtplib
from celery import Celery

from . import app
from .database import session, Photo

# Celery task queue setup
cel_app = Flask(__name__)
cel_app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
cel_app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery = Celery(cel_app.name, broker=cel_app.config['CELERY_BROKER_URL'])
celery.conf.update(cel_app.config)

# Constants
PROFILE_PAGE_URL = 'https://www.instagram.com/{}/'
SCRIPT_XPATH = "//script[@type='text/javascript' and contains(text(), 'sharedData')]/text()"
SCROLL_URL = 'https://www.instagram.com/graphql/query/?query_id={}&id={}&first={}&after={}'
PHOTOS_PER_SCROLL = 500
VALID_QUERY_ID = 17880160963012870  # required query parameter; appears to always be the same
FROM_EMAIL = 'youwantthephotos@gmail.com'
DOMAIN = 'http://0.0.0.0:8080'


@celery.task
def download_files(username, request_email):
    """Download files, zip together, and send email."""
    # visit main profile page to get user ID from HTML source
    res = requests.get(PROFILE_PAGE_URL.format(username))
    root = etree.HTML(res.content)

    # find imbedded JS data and convert to dictionary
    script = root.xpath(SCRIPT_XPATH)
    json_start = script[0].find('{')
    json_end = script[0].rfind('}')
    script = script[0][json_start:json_end+1]
    script = json.loads(script)

    # locate user ID and total photo count
    user_id = script['entry_data']['ProfilePage'][0]['logging_page_id']
    user_id = re.findall('[0-9]+', user_id)[0]
    photo_count = script['entry_data']['ProfilePage'][0]['user']['media']['count']

    # set default values before loop
    end_cursor = ''  # value that determines which photos to show next; blank value starts at top
    has_next_page = True
    photos_requested = 0
    photo_data = []

    # make AJAX request for photo information; repeat request until all photos found
    while has_next_page and (photos_requested <= photo_count):
        res = requests.get(SCROLL_URL.format(VALID_QUERY_ID, user_id, PHOTOS_PER_SCROLL, end_cursor))
        res_json = res.json()
        photos = res_json['data']['user']['edge_owner_to_timeline_media']['edges']
        photos = [x['node'] for x in photos]
        photo_data.extend(photos)
        end_cursor = res_json['data']['user']['edge_owner_to_timeline_media']['page_info']['end_cursor']
        has_next_page = res_json['data']['user']['edge_owner_to_timeline_media']['page_info']['has_next_page']
        photos_requested += PHOTOS_PER_SCROLL

    # put all photos in one zip file, and add info to database
    zf = zipfile.ZipFile('youwantthephotos_downloads/photos_{}_{}.zip'.format(username, user_id), mode='w')
    for p in photo_data:
        new_photo = Photo(
            username=username,
            instagram_id=p['id'],
            display_url=p['display_url'],
            likes=p['edge_liked_by']['count'],
            taken_at_timestamp=p['taken_at_timestamp'],
        )
        session.add(new_photo)
        session.commit()
        urllib.request.urlretrieve(p['display_url'], "youwantthephotos_downloads/{}_{}.jpg".format(username, p['id']))
        zf.write("youwantthephotos_downloads/{}_{}.jpg".format(username, p['id']))
        os.system("rm youwantthephotos_downloads/{}_{}.jpg".format(username, p['id']))
    zf.close()
    download_url = '{}/photos/download/photos_{}_{}'.format(DOMAIN, username, user_id)
    msg = "\r\n".join([
      "From: {}".format("You Want The Photos"),
      "To: {}".format(request_email),
      "Subject: Your photo download is ready!",
      "",
      "Your photos are READY! Download here: {}".format(download_url)
    ])
    email_username = 'youwantthephotos@gmail.com'
    password = os.environ['PHOTOS_PWD']
    server = smtplib.SMTP('smtp.gmail.com:587')
    server.ehlo()
    server.starttls()
    server.login(email_username, password)
    server.sendmail(FROM_EMAIL, request_email, msg)
    server.quit()


def intWithCommas(x):
    """Turn int into a comma-formatted number."""
    if x < 0:
        return '-' + intWithCommas(-x)
    result = ''
    while x >= 1000:
        x, r = divmod(x, 1000)
        result = ",%03d%s" % (r, result)
    return "%d%s" % (x, result)


@app.route("/", methods=['GET'])
def welcome():
    """Homepage displaying a few example photos."""
    res = requests.get(PROFILE_PAGE_URL.format("instagram"))
    root = etree.HTML(res.content)
    script = root.xpath(SCRIPT_XPATH)
    json_start = script[0].find('{')
    json_end = script[0].rfind('}')
    script = script[0][json_start:json_end+1]
    script = json.loads(script)
    first12 = script['entry_data']['ProfilePage'][0]['user']['media']['nodes']
    first12 = [x['thumbnail_src'] for x in first12]
    return render_template("welcome.html", first12=first12)


@app.route("/", methods=["POST"])
def welcome_post():
    """Submit username to visit user page."""
    username = request.form["username"]
    return redirect(url_for("user_photos", username=username))


@app.route("/photos/<username>", methods=["GET"])
def user_photos(username):
    """User page."""
    res = requests.get(PROFILE_PAGE_URL.format(username))
    if res.status_code == 200:
        root = etree.HTML(res.content)
        script = root.xpath(SCRIPT_XPATH)
        json_start = script[0].find('{')
        json_end = script[0].rfind('}')
        script = script[0][json_start:json_end+1]
        script = json.loads(script)
        first12 = script['entry_data']['ProfilePage'][0]['user']['media']['nodes']
        first12 = [x['thumbnail_src'] for x in first12]
        photo_count = script['entry_data']['ProfilePage'][0]['user']['media']['count']
        is_private = script['entry_data']['ProfilePage'][0]['user']['is_private']
        return render_template(
                                "user_photos.html",
                                first12=first12,
                                photo_count=photo_count,
                                formatted_photo_count_minus_9=intWithCommas(photo_count - 9),
                                username=username,
                                is_private=is_private
                                )
    if res.status_code == 404:
        flash("That user does not exist", "danger")
        return redirect(url_for("welcome"))


@app.route("/photos/<username>", methods=["POST"])
def user_photos_post(username):
    """Submit email and download photos."""
    download_files.apply_async(args=[username, request.form["email"]], countdown=5)
    flash('Downloading! We will email you a download link when it is ready.', "success")
    return redirect(url_for("user_photos", username=username))


@app.route("/photos/download/<download_name>", methods=["GET", "POST"])
def download_photos(download_name):
    """Download zip file."""
    return send_from_directory(directory=os.getcwd(), filename="youwantthephotos_downloads/{}.zip".format(download_name))
