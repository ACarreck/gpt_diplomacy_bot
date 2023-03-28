from flask import Flask, request, redirect
import requests
from settings import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

app = Flask(__name__)

# Replace these with your own values


@app.route('/authorize')
def authorize():
    discord_auth_url = f'https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds'
    return redirect(discord_auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'scope': 'identify guilds',
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
    response_json = response.json()

    if response.status_code == 200:
        access_token = response_json['access_token']
        user_response = requests.get('https://discord.com/api/users/@me', headers={'Authorization': f'Bearer {access_token}'})
        user_json = user_response.json()
        return f"Hello, {user_json['username']}!"
    else:
        return "An error occurred during the OAuth2 process.", 400

if __name__ == '__main__':
     app.run(host= '0.0.0.0', port=5000, debug=False)
