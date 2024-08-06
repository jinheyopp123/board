from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import pickle
import os
import json
import hashlib
import random
import string
from datetime import datetime
import markdown
from functools import wraps

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# 데이터 저장 및 로딩을 위한 파일 경로
DANCERS_FILE = 'dancers.pkl'
QUESTIONS_FILE = 'questions.pkl'
CSV_FILENAME = 'dancers_results.csv'
CONFIG_FILE = 'config.json'
USERS_FILE = 'users.pkl'
POSTS_FILE = 'posts.pkl'

# 데이터 모델
class Dancer:
    def __init__(self, name):
        self.name = name
        self.scores = []
        self.subjective_evaluations = []

    def add_score(self, score, question_index):
        while len(self.scores) <= question_index:
            self.scores.append(0)
        self.scores[question_index] += score

    def add_subjective_evaluation(self, evaluation):
        self.subjective_evaluations.append(evaluation)

    def total_score(self):
        return sum(self.scores)

class Question:
    def __init__(self, content):
        self.content = content

class User:
    def __init__(self, real_name, nickname, password, is_admin=False):
        self.real_name = real_name
        self.nickname = nickname
        self.password_hash = generate_password_hash(password)
        self.is_admin = is_admin

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_profile_image(self, size=80):
        # 랜덤 색상 및 문자열을 기반으로 프로필 이미지를 생성
        color = ''.join(random.choices(string.hexdigits, k=6))
        text = self.nickname[0].upper()
        return f'https://via.placeholder.com/{size}/{color}/FFFFFF?text={text}'

class Post:
    def __init__(self, title, content, author, created_at=None):
        self.title = title
        self.content = content
        self.author = author
        self.created_at = created_at or datetime.now()

# 전역 변수
dancers = []
questions = []
config = {}
users = []
current_user = None
posts = []

def load_config():
    global config
    try:
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        config = {"inspection": False, "preparing": False}

def save_data():
    with open(DANCERS_FILE, 'wb') as f:
        pickle.dump(dancers, f)
    with open(QUESTIONS_FILE, 'wb') as f:
        pickle.dump(questions, f)
    with open(USERS_FILE, 'wb') as f:
        pickle.dump(users, f)
    with open(POSTS_FILE, 'wb') as f:
        pickle.dump(posts, f)

def load_data():
    global dancers, questions, users, posts
    try:
        with open(DANCERS_FILE, 'rb') as f:
            dancers = pickle.load(f)
        with open(QUESTIONS_FILE, 'rb') as f:
            questions = pickle.load(f)
        with open(USERS_FILE, 'rb') as f:
            users = pickle.load(f)
        with open(POSTS_FILE, 'rb') as f:
            posts = pickle.load(f)
    except (FileNotFoundError, EOFError):
        pass

def reset_scores():
    global dancers
    for dancer in dancers:
        dancer.scores = []
        dancer.subjective_evaluations = []

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user is None or not current_user.is_admin:
            flash('관리자 권한이 필요합니다.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    load_config()  # Load the config file each time the index page is accessed
    if config.get("inspection"):
        return render_template('inspection.html')
    elif config.get("preparing"):
        return render_template('preparing.html')
    elif current_user:
        return redirect(url_for('board'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    global current_user
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        password = request.form.get('password')
        user = next((u for u in users if u.nickname == nickname), None)
        if user and user.check_password(password):
            current_user = user
            return redirect(url_for('board'))
        else:
            flash('닉네임 또는 비밀번호가 잘못되었습니다.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    global current_user
    current_user = None
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        real_name = request.form.get('real_name')
        nickname = request.form.get('nickname')
        password = request.form.get('password')
        if any(not field for field in [real_name, nickname, password]):
            flash('모든 필드를 채워야 합니다.')
        else:
            users.append(User(real_name, nickname, password))
            save_data()
            flash('회원 가입이 완료되었습니다. 로그인 해주세요.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/board')
def board():
    return render_template('board.html', posts=posts, user=current_user)

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        post = Post(title, content, current_user.nickname)
        posts.append(post)
        save_data()
        return redirect(url_for('board'))
    return render_template('create_post.html')

@app.route('/delete_post/<int:post_index>', methods=['POST'])
@login_required
def delete_post(post_index):
    if current_user.is_admin or posts[post_index].author == current_user.nickname:
        posts.pop(post_index)
        save_data()
        flash('게시물이 삭제되었습니다.')
    else:
        flash('삭제 권한이 없습니다.')
    return redirect(url_for('board'))

@app.route('/manage', methods=['GET', 'POST'])
@admin_required
def manage():
    if request.method == 'POST':
        if 'add_dancer' in request.form:
            name = request.form.get('dancer_name')
            if name:
                dancers.append(Dancer(name))
                flash(f'댄서 {name}이(가) 추가되었습니다.')
        elif 'add_question' in request.form:
            content = request.form.get('question_content')
            if content:
                questions.append(Question(content))
                flash(f'질문 "{content}"이(가) 추가되었습니다.')
        elif 'add_score' in request.form:
            dancer_name = request.form.get('dancer_name')
            question_content = request.form.get('question_content')
            score = request.form.get('score')
            try:
                score = int(score)
                if not (0 <= score <= 10):
                    raise ValueError
            except ValueError:
                flash('점수는 0에서 10 사이의 정수여야 합니다.')
                return redirect(url_for('manage'))

            dancer = next((d for d in dancers if d.name == dancer_name), None)
            question_index = next((i for i, q in enumerate(questions) if q.content == question_content), None)

            if dancer and question_index is not None:
                dancer.add_score(score, question_index)
                flash(f'{dancer.name}의 "{question_content}"에 대한 점수 {score}이(가) 추가되었습니다.')
            else:
                flash('댄서와 질문을 선택하세요.')
        elif 'add_subjective_evaluation' in request.form:
            dancer_name = request.form.get('dancer_name')
            evaluation = request.form.get('subjective_evaluation')
            if evaluation:
                dancer = next((d for d in dancers if d.name == dancer_name), None)
                if dancer:
                    dancer.add_subjective_evaluation(evaluation)
                    flash(f'{dancer.name}에 대한 주관적 평가가 추가되었습니다.')
                else:
                    flash('댄서를 선택하세요.')
            else:
                flash('주관적 평가 내용을 입력하세요.')
        elif 'export' in request.form:
            return export_to_csv()
        elif 'save' in request.form:
            save_data()
            flash('데이터가 저장되었습니다.')
        elif 'reset' in request.form:
            reset_scores()
            flash('모든 댄서의 점수와 주관적 평가가 초기화되었습니다.')

    return render_template('manage.html', dancers=dancers, questions=questions)

def export_to_csv():
    if not dancers:
        flash('댄서가 없습니다.')
        return redirect(url_for('manage'))

    # 데이터 준비
    data = {'댄서 이름': [dancer.name for dancer in dancers]}
    for i, question in enumerate(questions):
        data[question.content] = [dancer.scores[i] if i < len(dancer.scores) else 0 for dancer in dancers]
    data['총점'] = [dancer.total_score() for dancer in dancers]
    data['주관적 평가'] = ['; '.join(dancer.subjective_evaluations) for dancer in dancers]

    # CSV로 저장
    df = pd.DataFrame(data)
    df.to_csv(CSV_FILENAME, index=False, encoding='utf-8-sig')

    return send_file(CSV_FILENAME, as_attachment=True)

if __name__ == '__main__':
    load_data()
    app.run(host=0.0.0.0, port=5000, debug=True)
