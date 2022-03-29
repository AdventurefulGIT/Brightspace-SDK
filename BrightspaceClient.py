import requests
import getpass
import re



class Brightspace:

	def __init__(self, url, username="", password="", TwoFactorAuthentication=True):
		self.__url = url
		self.session = requests.Session()
		self.TwoFactorAuthentication = TwoFactorAuthentication

		username = username if username else input("Username: ")
		password = password if password else getpass.getpass()
		
		self._session(username, password)


	def _session(self, username, password):
		response = self.session.request(
			method = "GET",
			url = f"{self.__url}/d2l/login?sessionExpired=0&target=%2fd2l%2fhome"
		)
		
		response = self.session.request(
			method = "POST",
			url = f"{response.url.split('saml2')[0]}login",
			data = self.fetch_sign_in_data(response.text, username, password)
		)
		assert response.cookies.get_dict().get("ESTSAUTH") is not None, "Invalid Username or Password"

		if self.TwoFactorAuthentication:
			data = self.fetch_sign_in_data(response.text, username, password)
			headers = {
				"hpgrequestid": data["hpgrequestid"],
				"client-request-id": re.findall(r'"correlationId":"([^"]+)', response.text)[0],
				"canary": data["canary"],
				"Content-type": "application/json; charset=UTF-8",
				"hpgid": "1114",
				"Accept": "application/json",
				"hpgact": "2000",
				"Sec-GPC": "1",
			}

			response = self.session.request(
				method = "POST",
				url = "https://login.microsoftonline.com/common/SAS/BeginAuth",
				headers = headers,
				json = {
					"AuthMethodId": "OneWaySMS",
					"Method": "BeginAuth",
					"ctx": data["ctx"],
					"flowToken": data["flowToken"]
				}
			).json()
			assert response["Success"] == True, "Authentication Method Limit Reached"

			pin = input("PIN: ")

			response = self.session.request(
				method = "POST",
				url = "https://login.microsoftonline.com/common/SAS/EndAuth",
				headers = headers,
				json = {
					"Method": "EndAuth",
					"SessionId": response["SessionId"],
					"FlowToken": response["FlowToken"],
					"Ctx": response["Ctx"],
					"AuthMethodId": "OneWaySMS",
					"AdditionalAuthData": pin,
					"PollCount": "1"
				}
			).json()

			response = self.session.request(
				method = "POST",
				url = "https://login.microsoftonline.com/common/SAS/ProcessAuth",
				data = {
					"type": "18",
					"GeneralVerify": "false",
					"request": response["Ctx"],
					"mfaAuthMethod": "OneWaySMS",
					"canary": data["canary"],
					"otc": pin,
					"rememberMFA": "true",
					"login": username,
					"flowToken": response["FlowToken"],
					"hpgrequestid": data["hpgrequestid"],
					"sacxt": "",
					"hideSmsInMfaProofs": "false",
					"i19": "10299",
				}
			)

		response = self.session.request(
			method = "POST",
			url = "https://login.microsoftonline.com/kmsi",
			data = {
				"ctx": re.findall(r'"sCtx":"([^"]+)', response.text)[0],
				"flowToken": re.findall(r'"sFT":"([^"]+)', response.text)[0]
			}
		)

		response = self.session.request(
			method = "POST",
			url = f"{self.__url}/d2l/lp/auth/login/samlLogin.d2l",
			data = {
				"SAMLResponse": re.findall(r'"SAMLResponse" value="([^"]+)', response.text)[0]
			}
		)
		assert "/d2l/home" in response.url, "Login Failed"
		print(response.url)


	def fetch_sign_in_data(self, html, username, password):
		ctx = re.findall(r'ctx=([^"]*)"', html)
		data = {
			"i13": "0",
			"login": username,
			"loginfmt": username,
			"type": "11",
			"LoginOptions": "3",
			"lrt": "",
			"lrtPartition": "",
			"hisRegion": "",
			"hisScaleUnit": "",
			"passwd": password,
			"ps": "2",
			"psRNGCDefaultType": "",
			"psRNGCEntropy": "",
			"psRNGCSLK": "",
			"PPSX": "",
			"NewUser": "1",
			"FoundMSAs": "",
			"fspost": "0",
			"i21": "0",
			"CookieDisclosure": "0",
			"IsFidoSupported": "1",
			"isSignupPost": "0",
			"canary": re.findall(r'"canary":"([^"]*)', html)[0],
			"ctx": ctx[0] if len(ctx) > 0 else None,
			"hpgrequestid": re.findall(r'"sessionId":"([^"]+)', html)[0],
			"flowToken": re.findall(r'"sFT":"([^"]+)', html)[0],
			"i19": "5701",
		}
		return data


