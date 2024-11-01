import os 
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from helper_functions import login_required, search_wikidata
import bcrypt
from password_validator import PasswordValidator
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import json
from json.decoder import JSONDecodeError
import plotly.graph_objs as go
import plotly.io as pio



app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)






db = SQL("sqlite:///anything_data.db")

subjects = ['Science', 'Social Studies', 'Culture', 'Entertainment', 'Math', 'Literature']



password_schema = PasswordValidator()
password_schema \
    .min(8) \
    .max(100) \
    .has().uppercase() \
    .has().lowercase() \
    .has().digits() \
    .has().symbols() \
    .has().no().spaces() \






@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers.Expires = 0
    response.headers.Pragma = "no-cache"
    return response




@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    session.clear()


    if request.method == "POST":



        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )



        if len(rows) != 1 or not bcrypt.checkpw(request.form.get("password").encode(), rows[0]["hash"]):
            flash("invalid username and/or password", "error")
            return render_template("login.html")





        session["user_id"] = rows[0]["id"]

        session["username"] = rows[0]["username"]


        return redirect("/")


    else:
        return render_template("login.html")


@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if session["user_id"]:

            if request.method == "POST":

                quiz_subject = request.form.get("quiz-subject")
                quiz_score = float(request.form.get("score-average"))

                quiz_totals_data = db.execute("SELECT quiz_totals.quizzes_taken, quiz_totals.subject_average_score FROM quiz_totals WHERE quiz_totals.user_id = :user_id AND quiz_totals.quiz_subjects = :quiz_subject", user_id=session["user_id"], quiz_subject=quiz_subject)
                
                # Calculating average score per subject for bar chart

                quizzes_taken = int(quiz_totals_data[0]["quizzes_taken"])

                subject_average_score = float(quiz_totals_data[0]["subject_average_score"])

                new_average_score = round(((subject_average_score * quizzes_taken) + quiz_score) / (quizzes_taken + 1), 1)

                quizzes_taken += 1

                quiz_score = (f"{quiz_score}%")

                # update quiz_totals table

                db.execute("UPDATE quiz_totals SET quizzes_taken = ?, subject_average_score = ? WHERE user_id = ? AND quiz_subjects = ?", quizzes_taken, new_average_score, session["user_id"], quiz_subject)

                # Insert new column into quiz_history table

                db.execute("INSERT INTO quiz_history (user_id, quiz_topic, quiz_description, quiz_image, quiz_score, quiz_subject) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], request.form.get('quiz_topic'), request.form.get('quiz_description'), request.form.get('quiz_image'), quiz_score, quiz_subject)

                

                return redirect("/")


            



            # IF METHOD IS GET

            # Display quiz history

            rows = db.execute("""
                SELECT DISTINCT quiz_history.quiz_topic, quiz_history.quiz_image, quiz_history.quiz_description, quiz_history.created_at, quiz_history.quiz_subject, quiz_history.quiz_score
                FROM quiz_history
                WHERE quiz_history.user_id = :user_id
                ORDER BY quiz_history.id DESC
                LIMIT 10
                """, user_id=session["user_id"])
            

            # Create Bar Chart

            bar_chart_info = db.execute("SELECT quiz_totals.subject_average_score, quiz_totals.quiz_subjects, quiz_totals.quizzes_taken FROM quiz_totals WHERE quiz_totals.user_id = :user_id", user_id=session["user_id"])

            bar_chart_headings = []

            bar_chart_quizaverages = []

            for item in bar_chart_info:

                bar_chart_headings.append(f"{item['quiz_subjects']} ({item['quizzes_taken']})")

                item_score = int(item['subject_average_score'])

                bar_chart_quizaverages.append(item_score)



            
            fig = go.Figure(data=[go.Bar(
                x=bar_chart_headings, 
                y=bar_chart_quizaverages,
                text=[f"{score}%" for score in bar_chart_quizaverages],
                textposition='auto',
                marker_color=['#FF9999', '#66B3FF', '#99FF99', '#FFCC99', '#FFD700', '#FFB6C1']
            )])

            fig.update_layout(
                title='Average Quiz Score by Subject',
                title_font=dict(size=26, color='black'),
                xaxis_title='Subjects (Amount of quizzes taken on subject)',
                xaxis_title_font=dict(size=22, color='black'),
                xaxis=dict(tickfont=dict(size=20, color='black')),
                yaxis_title='Average Percentage',
                yaxis_title_font=dict(size=22, color='black'),
                yaxis=dict(range=[0, 100], tickformat=".0%", tickvals=[0, 20, 40, 60, 80, 100], ticktext=["0%", "20%", "40%", "60%", "80%", "100%"], tickfont=dict(size=16, color='black')),
                plot_bgcolor='rgba(255, 255, 255, 0)',
                paper_bgcolor='rgba(255, 255, 255, 0)',
                margin=dict(l=60, r=50, t=60, b=50),
            )

            # Convert Plotly figure to JSON and pass it to the frontend
            graph_json = pio.to_json(fig)

            return render_template("index.html", username=session["username"], rows=rows, graph_json=graph_json)
    except KeyError:

        return render_template("index_nologin.html")







@app.route("/history", methods=["GET", "POST"])
@login_required
def history():

    rows = db.execute("""
                SELECT DISTINCT quiz_history.quiz_topic, quiz_history.quiz_image, quiz_history.quiz_description, quiz_history.created_at, quiz_history.quiz_score
                FROM quiz_history
                WHERE quiz_history.user_id = :user_id
                ORDER BY quiz_history.id DESC
                """, user_id=session["user_id"])


    
    return render_template("history.html", rows=rows)
    



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST": 
        username = request.form.get("username") 
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")


        if password != confirmation:
            flash("Passwords do not match", "error")
            return render_template("signup.html")

        user_result = db.execute("SELECT username FROM users WHERE username = ?", username)
        if user_result:
            flash("Username is already taken. Please try again", "error")
            return render_template("signup.html")

        if not password_schema.validate(password):
            flash("Password does not meet security requirements. Please try again.")
            return render_template("signup.html")

        password_bytes = password.encode()


        # Initializing database 

        db.execute("INSERT INTO users (username, hash, coin) VALUES(?, ?, ?)", username, bcrypt.hashpw(password_bytes, bcrypt.gensalt()), 0)

        user_data = db.execute("SELECT id FROM users WHERE username = ?", username)

        user_id = user_data[0]["id"]

        for subject in subjects:
            db.execute("INSERT INTO quiz_totals (user_id, quizzes_taken, quiz_subjects, subject_average_score) VALUES (?, ?, ?, ?)", user_id, 0, subject, 0)
            
            
        return redirect("/login")

    return render_template("signup.html")

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


@app.route("/quiz_select", methods=["GET", "POST"])
def quiz_select():

    if request.method == "POST":
        query = request.form.get("topic")  

        results_list = search_wikidata(query)



        # Render the quiz selection page with the initial set of results
        return render_template("quiz_select.html", results_list=results_list, query=query)



@app.route("/start_quiz", methods=["GET", "POST"])
def start_quiz():
    if request.method == "POST":
        quiz_topic = request.form.get("item_label")
        quiz_description = request.form.get("item_description")
        quiz_image = request.form.get("image_url")
        return render_template("start_quiz.html", quiz_topic=quiz_topic, quiz_description=quiz_description, quiz_image=quiz_image)



@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if request.method == "POST":

        timer = request.form.get('timer')
        timer = request.form.get('timerSelect') if timer == "Yes" else timer
        questions = request.form.get('questions')
        questions = request.form.get('customSelect') if questions == "custom" else questions
        difficulty = request.form.get('difficulty')
        quiz_topic = request.form.get("quiz_topic")
        quiz_description = request.form.get("quiz_description")
        quiz_image = request.form.get("quiz_image")

        if not timer or not questions or not difficulty:
            flash("Please make sure all settings are chosen before starting quiz.", "error")
            quiz_description = request.form.get("quiz_description")
            quiz_image = request.form.get("quiz_image")
            return render_template("start_quiz.html", quiz_topic=quiz_topic, quiz_description=quiz_description, quiz_image=quiz_image)
        


        prompt_text = f"""
            I need to create {questions} multiple choice questions on {quiz_topic} ({quiz_description}) that are of {difficulty} difficulty and have four choices per question.
            Give the answer to each question right after the question is displayed.
            Provide a 1-3 sentence explanation for each answer.
            Use Wikipedia and other websites with information on {quiz_topic} given to create your questions.
            If the topic is Math-related use your own knowledge to create Math questions and answers rather than other websites
            Ensure all questions/answers are as credible as possible and the answers are factual.
            Determine whether the topic given is in the subject of Science, Social Studies, Culture, Entertainment, Math, or Literature.
            Return this as a list of dictionaries in the following structure where it is done EXACTLY like this example (this is just example text with two questions):
            Add the subject to just the last dictionary in the list of dictionaries returned.

            [{{ "question":"Who won the 2012 NBA Finals?", "options":[ "Oklahoma City Thunder", "Miami Heat", "Los Angeles Lakers", "Boston Celtics" ], "answer":"Miami Heat", "explanation":"The Miami Heat defeated the Oklahoma City Thunder to win the NBA Championship in 2012."}}, {{ "question":"Who was the Most Valuable Player (MVP) of the 2012 NBA Finals?", "options":[ "Kevin Durant", "LeBron James", "Dwyane Wade", "Russell Westbrook" ], "answer":"LeBron James", "explanation":"LeBron James of the Miami Heat was named the 2012 Finals MVP.", "subject": "Entertainment"}}]
            """
        

        _ = load_dotenv(find_dotenv())

        

        test_var = 2

        if test_var == 2:
            client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'),)
            chat_completion = client.chat.completions.create(
            messages=[
               {
            "role": "user",
            "content": prompt_text,
                }
            ],
            model="gpt-4",

            )   

            try:
                questions_list = chat_completion.choices[0].message.content
                questions_list_for_html = json.loads(questions_list)
            except JSONDecodeError:
                questions_list = None
                questions_list_for_html = None


            

        
        if test_var == 3:
            questions_list = questions_list = [{ "question":"Who won the 2012 NBA Finals?", "options":[ "Oklahoma City Thunder", "Miami Heat", "Los Angeles Lakers", "Boston Celtics" ], "answer":"Miami Heat", "explanation":"The Miami Heat defeated the Oklahoma City Thunder to win the NBA Championship in 2012.", "media":"" }, { "question":"Who was the Most Valuable Player (MVP) of the 2012 NBA Finals?", "options":[ "Kevin Durant", "LeBron James", "Dwyane Wade", "Russell Westbrook" ], "answer":"LeBron James", "explanation":"LeBron James of the Miami Heat was named the 2012 Finals MVP.", "media":"" }, { "question":"How many games did the 2012 NBA Finals last?", "options":[ "5 games", "6 games", "7 games", "4 games" ], "answer":"5 games", "explanation":"The 2012 NBA Finals lasted 5 games, with the Miami Heat winning the series 4-1.", "media":"" }, { "question":"Which team did the Oklahoma City Thunder beat in the Western Conference Finals to reach the 2012 NBA Finals?", "options":[ "San Antonio Spurs", "Los Angeles Lakers", "Denver Nuggets", "Dallas Mavericks" ], "answer":"San Antonio Spurs", "explanation":"The Thunder defeated the San Antonio Spurs in the Western Conference Finals.", "media":"" }, { "question":"Which player from the Miami Heat team scored the highest number of points in Game 5 of the 2012 NBA Finals?", "options":[ "Dwyane Wade", "LeBron James", "Chris Bosh", "Mario Chalmers" ], "answer":"LeBron James", "explanation":"LeBron James scored the highest number of points (26) for Miami Heat in Game 5.", "media":"" }, { "question":"Who coached the Miami Heat during the 2012 NBA Finals?", "options":[ "Pat Riley", "Erik Spoelstra", "Phil Jackson", "Gregg Popovich" ], "answer":"Erik Spoelstra", "explanation":"Erik Spoelstra was the head coach of the Miami Heat during the 2012 NBA Finals. Spoelstra helped lead the team to its second NBA Championship.", "media":"" }, { "question":"How many points did Kevin Durant average in the 2012 NBA Finals?", "options":[ "32.2 points", "35.2 points", "30.6 points", "34.0 points" ], "answer":"30.6 points", "explanation":"Kevin Durant averaged 30.6 points per game in the 2012 NBA Finals.", "media":"" }, { "question":"What was the venue for Game 1 of the 2012 NBA Finals?", "options":[ "Staples Center", "Chesapeake Energy Arena", "AmericanAirlines Arena", "TD Garden" ], "answer":"Chesapeake Energy Arena", "explanation":"Game 1 of the 2012 NBA Finals was played at the Chesapeake Energy Arena, home of the Oklahoma City Thunder.", "media":"" }, { "question":"In which quarter did Miami Heat score the most points in Game 5 of the 2012 NBA Finals?", "options":[ "1st Quarter", "2nd Quarter", "3rd Quarter", "4th Quarter" ], "answer":"2nd Quarter", "explanation":"Miami Heat scored the most points (34 points) in the 2nd quarter of Game 5.", "media":"" }, { "question":"Check the clip and indicate who made the final basket in Game 5 of the 2012 NBA Finals?", "options":[ "Dwyane Wade", "LeBron James", "Mario Chalmers", "Chris Bosh" ], "answer":"LeBron James", "explanation":"LeBron James made the final basket in Game 5 of the 2012 NBA Finals.", "subject": "Entertainment"}]

            questions_list_for_html = questions_list


        return render_template("quiz.html", questions_list=questions_list, questions_length=questions, timer=timer, questions_list_for_html=questions_list_for_html, quiz_topic=quiz_topic, quiz_description=quiz_description, quiz_image=quiz_image)




if __name__ == "__main__":
    app.run(debug=True)




