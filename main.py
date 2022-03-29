from bs4 import BeautifulSoup
import BrightspaceClient
import datetime
import imgkit
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
            answer = True if input("Two Factor Required?(0/1): ") == 1 else False
            self.session = BrightspaceClient.Brightspace(url, TwoFactorAuthentication=True).session
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

        
    def get_course_assignments(self, course_id, due_check=True):
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

                    if due_check:
                        if assignment_date != "Unknown":
                            if datetime.datetime.strptime(assignment_date, "%b %d, %Y %I:%M %p") <= datetime.datetime.now():
                                continue
                    assignments[list(assignments.keys())[-1]].append(assignment)    
            return assignments#json.dumps(assignments, indent=4, sort_keys=False)
        

    def generate_display(self, term, assignments):
        page = f''' 
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.1/dist/css/bootstrap.min.css" integrity="sha384-zCbKRCUGaJDkqS1kPbPd7TveP5iyJE0EjAuZQTgFLD2ylzuqKfdKlfG/eSrtxUkn" crossorigin="anonymous">
            <script src="https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.slim.min.js" integrity="sha384-DfXdz2htPH0lsSSs5nCTpuj/zy4C+OGpamoFVy38MVBnE+IbbVYUew+OrCXaRkfj" crossorigin="anonymous"></script>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.1/dist/js/bootstrap.bundle.min.js" integrity="sha384-fQybjgWLrvvRgtW6bFlB7jaZrFsaBXjsOMm/tB9LTS58ONXgqbR9W8oWht/amnpF" crossorigin="anonymous"></script>
 
            <h1>{term}<h1>
        '''

        def add_class(course, course_content):
            html = f"<h3 class='font-weight-bold'>{course}</h3>"

            for value in course_content:
                if len(course_content[value]) == 0:
                    continue
                html += f"<h4 class><u>{value}</u></h4>\n"

                html += "<table class='table'><tr><th class='w-50 text-left'>Name</th><th class='w-50 text-left'>Due Date</th></tr>\n"
                
                for assign in course_content[value]:
                    html += f"<tr><td>{assign['Name']}</td><td>{assign['Due Date']}</td></tr>"
                html += "</table>"

                

            return html if len(html.split('\n')) != 1 else ""

        for course in assignments:
            page += add_class(course, assignments[course])

        return imgkit.from_string(page, False, options={'width': 800, 'disable-smart-width': ''})
        
if __name__ == "__main__":
    url = input("Url: ")
    client = BSManager(url)

    semesters = client.get_semesters()
    for index, semester in enumerate(semesters):
        print(f"{index + 1}: {semester}")

    semester = list(semesters.keys())[int(input("\nSelect a semester: "))-1]

    courses = client.get_courses(semesters[semester])
    details = {}
    for course in courses:
        details[client.get_course_name(course)] = client.get_course_assignments(course)

    md = client.generate_display(semester, details)

    #print(md)
    #Html2Image().screenshot(md, save_as="out.png")
    