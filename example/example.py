#!/usr/bin/python3
import sys
import os
import o11
import base64
import json
import time
from dateutil import parser
from deep_translator import GoogleTranslator

user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'

user=o11.parse_params(sys.argv, 'user')
password=o11.parse_params(sys.argv, 'password')
device=o11.parse_params(sys.argv, 'device')
pin=o11.parse_params(sys.argv, 'pin')

if user == "" or password == "":
    print("no account specificed")
    sys.exit(1)

if len(device) != 36:
    print("device must be a UUID")
    sys.exit(1)

id=o11.parse_params(sys.argv, 'id')
text=o11.parse_params(sys.argv, 'text')
srclang=o11.parse_params(sys.argv, 'srclang')
dstlang=o11.parse_params(sys.argv, 'dstlang')
action=o11.parse_params(sys.argv, 'action')
url=o11.parse_params(sys.argv, 'url')

bind=o11.parse_params(sys.argv, 'bind')
proxy=o11.parse_params(sys.argv, 'proxy')
doh=o11.parse_params(sys.argv, 'doh')
dns=o11.parse_params(sys.argv, 'dns')
worker=o11.parse_params(sys.argv, 'worker')

cdm=o11.parse_params(sys.argv, 'cdm')
drm=o11.parse_params(sys.argv, 'drm')
kid=o11.parse_params(sys.argv, 'kid')
pssh=o11.parse_params(sys.argv, 'pssh')
challenge=o11.parse_params(sys.argv, 'challenge')
licenseurl=o11.parse_params(sys.argv, 'licenseurl')
licenseparams=o11.parse_params(sys.argv, 'licenseparams')

heartbeaturl=o11.parse_params(sys.argv, 'heartbeaturl')
heartbeatparams=o11.parse_params(sys.argv, 'heartbeatparams')

o11Session = o11.session(bind=bind, proxy=proxy,  worker=worker, doh=doh, dns=dns)
req = o11Session.get_session()

if doh != "":
    o11.dns(doh)
elif dns != "":
    o11.dns(dns)

if action == "subtitles":
    if srclang == "":
        srclang = "auto"
    output = {
            "Text": GoogleTranslator(source=srclang, target=dstlang).translate(text)
            }
    print(json.dumps(output))
    sys.exit(1)

if challenge == "cert":
    challenge = "CAQ="

authFile = '/example_' + user + '.tokens'

headers = {}

def pair():
    print("pairing...", flush=True)

    response = req.get()
    try:
        code = response.json()['code']
        print("Please go to ... and enter code " + code, flush=True)
    except:
        print(response.text, flush=True)
        sys.exit(1)

    print("please enter received code: ", flush=True)
    code = input()

    while True:
        response = req.get()
        try:
            response.json()['token']
            json.dump(response.json(), open(os.path.abspath(os.path.dirname(__file__)) + authFile, 'w'))
            print("pairing done", flush=True)
            break
        except:
            pass

        time.sleep(1)

def login():
    print("logging in...", file=sys.stderr)

    # Get token
    response = req.get()
    try:
        response.json()['token']
        json.dump(response.json(), open(os.path.abspath(os.path.dirname(__file__)) + authFile, 'w'))
    except:
        output = {
                "ErrorCode": 401,
                "ErrorMessage": "auth failed"
                }
        print(json.dumps(output))
        sys.exit(0)

    print("logged in successfully", file=sys.stderr)

def refresh():
    print("refreshing tokens...", file=sys.stderr)

    try:
        auth = json.load(open(os.path.abspath(os.path.dirname(__file__)) + authFile))
    except:
        return "error"

    # Get token
    response = req.get()
    try:
        response.json()['token']
    except:
        print(response.text, file=sys.stderr)
        return "error"

    auth.update(response.json())
    json.dump(auth, open(os.path.abspath(os.path.dirname(__file__)) + authFile, 'w'))

    print("tokens refreshed successfully", file=sys.stderr)

def do_action():

    if action == "pair":
        pair()
        sys.exit()
    elif action == "login":
        login()
        sys.exit()

    try:
        auth = json.load(open(os.path.abspath(os.path.dirname(__file__)) + authFile))
    except:
        return "error"

    if action == "channels":
        output = {}
        output['Channels'] = []

        response = req.get()
        try:
            for chan in response.json():
                channel  = {}
                channel['Name'] = chan['Name']
                channel['SortId'] = 0
                channel['EpgId'] = ""
                channel['Mode'] = "live"
                channel['ScriptParams'] = 'id=' + str(chan['Id'])
                channel['SessionManifest'] = True
                channel['CdmType'] = "widevine"
                channel['UseCdm'] = True
                channel['Video'] = 'best'
                channel['OnDemand'] = True
                channel['SpeedUp'] = True
                channel['LogoUrl'] = ""
                channel['Info'] = "unsubscribed"
                output['Channels'].append(channel)

            print(json.dumps(output, indent=2))
        except:
            print(response.text, file=sys.stderr)
            return "error"

    elif action == "vod":
        output = {}
        output['Vod'] = []

        response = req.get()
        try:
            for item in response.json():
                vod  = {}
                vod['Name'] = item['Name']
                vod['Category'] = ''
                vod['Description'] = ''
                vod['Mode'] = "vod"
                vod['SessionManifest'] = True
                vod['ScriptParams'] = 'id=' + str(item['Id'])
                vod['CdmType'] = "widevine"
                vod['UseCdm'] = True
                vod['Video'] = 'best'
                output['Vod'].append(vod)

            print(json.dumps(output, indent=2))
        except:
            print(response.text, file=sys.stderr)
            return "error"

    elif action == "events":
        output = {}
        output['Events'] = []

        response = req.get()
        try:
            for ev in response.json():
                event  = {}
                event['Name'] = ev['Name']
                event['Mode'] = "live"
                event['SessionManifest'] = True
                event['ScriptParams'] = 'id=' + str(ev['Id'])
                event['CdmType'] = "widevine"
                event['UseCdm'] = True
                event['Video'] = 'best'
                event['OnDemand'] = True
                event['SpeedUp'] = True
                event['Start'] = int(parser.parse(ev['start_date']).timestamp())
                event['End'] = int(parser.parse(ev['end_date']).timestamp())
                output['Events'].append(event)

            print(json.dumps(output, indent=2))
        except:
            print(response.text, file=sys.stderr)
            return "error"

    elif action == "epg":
        output = {}
        output['Epg'] = {}
        output['Epg']['Channels'] = []

        channels = req.get()
        try:
            for chan in channels.json():
                channel = {}
                channel['Name'] = chan['Name']
                channel['EpgId'] = ""
                channel['Lang'] = 'en'
                channel['Entries'] = []

                items = req.get()
                for item in items.json():
                    entry  = {}
                    entry['Title'] = item['Title']
                    entry['Description'] = item['Description']
                    entry['Lang'] = item['Lang']
                    entry['Start'] = int(parser.parse(item['start_date']).timestamp())
                    entry['End'] = int(parser.parse(item['end_date']).timestamp())
                    channel['Entries'].append(entry)

                output['Epg']['Channels'].append(channel)
                
            print(json.dumps(output, indent=2))
        except:
            print(response.text, file=sys.stderr)
            return "error"

    elif action == "heartbeat":
        output = {
                "ManifestUrl": response.json()['mpdUrl'],
                "Headers": {
                    "Manifest": {
                        'User-Agent': user_agent
                        },
                    "Media": {
                        'User-Agent': user_agent
                        }
                    },
                "Heartbeat": {
                    "Url": '',
                    "Params": '',
                    "PeriodMs": 5*60*1000
                    },
                }
        print(json.dumps(output))

    elif action == "manifest":
        try:
            output = {
                    "Cdn": [],
                    "ManifestUrl": response.json()['mpdUrl'],
                    "ManifestExpiration": 0, # Unix timestamp
                    "Headers": {
                        "Manifest": {
                            'User-Agent': user_agent
                            },
                        "Media": {
                            'User-Agent': user_agent
                            }
                        },
                    "Heartbeat": {
                        "Url": '',
                        "Params": '',
                        "PeriodMs": 5*60*1000
                        },
                    "License": {
                        "Url": '',
                        "Params": ''
                        }
                    }
            for cdn in [ '' ]:
                response = req.get("", headers=headers)
                output['Cdn'].append({ "Name": cdn, "ManifestUrl": mpd_url })
                output['ManifestUrl'] =  mpd_url
            print(json.dumps(output))
        except:
            print(response.text, file=sys.stderr)
            return "error"

    elif action == "cdm" and cdm == "internal":
        # return license from challenge
        response = req.post(licenseurl, headers=headers, data=base64.b64decode(challenge))
        response_b64 = str(base64.b64encode(response.content), 'ascii')
        if response_b64.startswith('CA'):
            output = {
                    "CdmAnswer": response_b64
                    }
            print(json.dumps(output))
        else:
            print(response.text, file=sys.stderr)
            return "error"

    elif action == "cdm" and cdm == "external":
        output = {
                "CdmAnswer": keys
                }
        print(json.dumps(output))

    elif action == "pssh":
        output = {
                "ProcessedPssh": pssh
                }
        print(json.dumps(output))
    elif action == "downloadmanifest":
        response = req.get(url)
        output = {
                "ErrorCode": response.status_code,
                "Payload": base64.b64encode(response.content).decode()
                }
        print(json.dumps(output))
    elif action == "downloadmedia":
        response = req.get(url)
        output = {
                "ErrorCode": response.status_code,
                "Payload": base64.b64encode(response.content).decode()
                }
        print(json.dumps(output))
    else:
        print("invalid action: " + action)

if do_action() == "error":
    if refresh() == "error":
        login()
    if do_action() == "error":
        sys.exit(1)
