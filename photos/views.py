from flask import render_template, request, redirect, url_for, flash, g
from flask.ext.login import login_user, login_required, current_user, logout_user
from werkzeug.security import check_password_hash
from lxml import etree
import json
import requests
import re
import locale

from . import app
from .database import session, Photo

PROFILE_PAGE_URL = 'https://www.instagram.com/{}/'
SCRIPT_XPATH = "//script[@type='text/javascript' and contains(text(), 'sharedData')]/text()"
SCROLL_URL = 'https://www.instagram.com/graphql/query/?query_id={}&id={}&first={}&after={}'
PHOTOS_PER_SCROLL = 500
VALID_QUERY_ID = 17880160963012870 # required query parameter; appears to always be the same

def after_this_request(func):
    if not hasattr(g, 'call_after_request'):
        g.call_after_request = []
    g.call_after_request.append(func)
    return func

@app.after_request
def per_request_callbacks(response):
    for func in getattr(g, 'call_after_request', ()):
        response = func(response)
    return response

def intWithCommas(x):
    if x < 0:
        return '-' + intWithCommas(-x)
    result = ''
    while x >= 1000:
        x, r = divmod(x, 1000)
        result = ",%03d%s" % (r, result)
    return "%d%s" % (x, result)

@app.route("/", methods=['GET'])
def welcome():
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
    username = request.form["username"]
    return redirect(url_for("user_photos", username=username))

@app.route("/photos/<username>", methods=["GET"])
def user_photos(username):
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
                                first12 = first12,
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
    
    flash("Downloading. You will receive an email within an hour with a download link.", "success")
    #need to implement actual downloading of files. Currently just saves links to database.
    return redirect(url_for("user_photos", username=username))
    
    # set default values before loop
    end_cursor = '' # value that determines which photos to show next; blank value starts at top
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
    for p in photo_data:
        new_photo = Photo(
            username = username,
            instagram_id = p['id'],
            display_url = p['display_url'],
            likes = p['edge_liked_by']['count'],
            taken_at_timestamp = p['taken_at_timestamp'],
        )
        session.add(new_photo)
        session.commit()
