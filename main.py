from bs4 import BeautifulSoup
import BrightspaceClient
import pickle
import json
import re

class BSManager:
    def __init__(self, url):
        self.__url = url
        try:
            self.session = pickle.load(open("./session.bkl", 'rb'))
            if not "/d2l/home" in self.session.get(url).url:
                raise Exception("Dead session")
        except:
            self.session = BrightspaceClient.Brightspace(url, TwoFactorAuthentication=input("On Campus?: ")).session
            with open('./session.bkl', 'wb') as f:
                pickle.dump(self.session, f)

        self.xsrf, self.user_id = self.get_initiation_data()
        self.session.headers.update({"Authorization":self.get_authorization_token(self.xsrf)})


    def get_initiation_data(self):
        response = self.session.request(
            method = "GET",
            url = f"{self.__url}/d2l/home#_"
        )
        return (re.findall(r"'XSRF\.Token','([^']+)", response.text)[0], re.findall(r"'Session\.UserId','(\d+)'", response.text)[0])


    def get_authorization_token(self, xsrf):
        response = self.session.request(
            method = "POST",
            url = f"{self.__url}/d2l/lp/auth/oauth2/token", 
            headers = {"x-csrf-token": xsrf},
            data = {"scope": "*:*:*"}
        )
        return "Bearer %s" % response.json()["access_token"]
    

    def get_semesters(self):
        response = self.session.request(
            method = "GET",
            url = f"{self.__url}/d2l/api/le/manageCourses/courses-searches/{self.user_id}/BySemester?desc=0"
        )

        classes = {}
        for semester in response.json()["actions"]:
            classes[semester["title"]] = {"user":semester["href"], "semester":semester["fields"][0]["value"]}
        
        return classes


    def get_courses(self, semester):
        response = self.session.request(
            method = "GET",
            url = semester["user"], 
            params = (
                ("parentOrganizations", semester["semester"]),
                ("roles", ""),
                ("search", ""),
                ("embedDepth", "0"),
                ("pageSize", "20"),
                ("promotePins", "true"),
                ("sort", "current")
            )
        )

        courses = []
        for course in response.json()["entities"]:
            course = self.session.request(
                method = "GET",
                url = course["href"]
            ).json()["actions"][0]["href"].split("/")[-1]
            courses.append(course)
        return courses
    

    def get_course_name(self, course_id):
        response = self.session.request(
            method = "GET",
            url = f"{self.__url}/d2l/home/{course_id}"
        )
        return re.findall(r"<title>Homepage - (.*)<\/title>", response.text)[0]

        
    def get_course_assignments(self, course_id):
            response = self.session.request(
                method = "GET",
                url = f"{self.__url}/d2l/lms/dropbox/user/folders_list.d2l?ou={course_id}"
            )

            soup = BeautifulSoup(response.text, "html.parser")

            titles = soup.find("table", attrs={"class":"d2l-table d2l-grid d_gd"})
            titles.find("tr").extract()

            assignments = {}
            
            for title in titles:
                if title.get("class") == ["d_ggl2", "d_dbold"]:
                    assignments[title.get_text()] = []
                else:
                    header = title.find("th")
                    assignment_name = header.find("a", attrs={"class":"d2l-link d2l-link-inline"})
                    if assignment_name is None:
                        assignment_name = title.find("label").get_text()
                    else:
                        assignment_name = assignment_name.get_text()
                    
                    assignment_date = title.find_all("td")[-1].get_text()
                    assignment_date = assignment_date.replace('\u00a0', "Unknown")
                    
                    assignment = {"Name":assignment_name, "Due Date":assignment_date}
                    assignments[list(assignments.keys())[-1]].append(assignment)    
            return json.dumps(assignments, indent=4, sort_keys=False)
        



if __name__ == "__main__":
    url = input("Url: ")
    client = BSManager(url)

    semesters = client.get_semesters()
    for index, semester in enumerate(semesters):
        print(f"{index + 1}: {semester}")

    semester = list(semesters.keys())[int(input("\nSelect a semester: "))-1]

    courses = client.get_courses(semesters[semester])
    for course in courses:
        print(client.get_course_name(course))
        print(client.get_course_assignments(course))