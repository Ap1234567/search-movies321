from typing import Any, List

import bcrypt
from flask import Flask, abort, render_template, request, session, url_for
from playhouse.shortcuts import model_to_dict
import peewee
from werkzeug.utils import redirect

from migrate_to_postgress import *

# from scripts import TABLES, get_table_class


app = Flask(__name__)
app.config.from_pyfile('config.py')

TABLES = [
    Genres, Companies, Movies, Users,
    MoviesGenres, MoviesCompanies, Comments
]


def get_table_module(table_name):
    name = table_name.title()
    tables = (t for t in TABLES if t.__name__ == name)
    return next(tables, None)


@app.route('/movie/<int:movie_id>')
def show_movie_page(movie_id: int) -> List[Any]:
    # movie = Movies.select().where(Movies.id == movie_id).get()
    try:
        movie = Movies.get_by_id(movie_id)
    except peewee.DoesNotExist:
        abort(404, f'Error: movie {movie_id} does not exists')
    movie_dict = model_to_dict(movie)
    return render_template('movie.j2', **movie_dict)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.j2')

    salt = bcrypt.gensalt(prefix=b'2b', rounds=10)
    unhashed_password = request.form['password'].encode('utf-8')
    hashed_password = bcrypt.hashpw(unhashed_password, salt)
    fields = {
        **request.form,
        'password': hashed_password,
        'level': 1,
    }
    # usersnames = list(Users.select(Users.username))
    # emails = Users.select(Users.email)
    # if fields["username"] in usersnames:
    #     abort(422, f"This username is already occupied, please choose another.")
    # if fields["email"] in emails:
    #     abort(422, f"This email is already occupied, please choose another.")
    Users.create(**fields)
    return 'Success!'

# @app.route('/')
def get_all(table_name):
    table = get_table_module(table_name)
    entities = table.select()
    return entities


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.j2')
    username = request.form['username']
    if username is None:
        return abort(400, 'No username supplied')

    try:
        user = Users.select().where(Users.username == username).get()
    except peewee.DoesNotExist:
        return abort(404, f'User {username} does not exists')

    password = request.form['password'].encode('utf-8')
    real_password = str(user.password).encode('utf-8')
    if not bcrypt.checkpw(password, real_password):
        return abort(403, 'Username and password does not match')

    session['username'] = user.username
    # session['level'] = user.level
    return render_template('search_movies.j2', 
            all_genres=get_all("genres"), 
            all_companies=get_all("companies"))
    # return redirect(url_for('get_all_names'))


# @app.route('/search_movies', methods=['GET', 'POST'])
# def search_movies():
#     if session.get('username') is None:
#         return abort(403, 'You must be logged in to view the movies page')

#     if request.method == 'GET':
#         return render_template('search_movies.j2', 
#             all_genres=get_all("genres"), 
#             all_companies=get_all("companies"))

#     movie_name = request.args.get("movie_name")
#     genre = request.args.get("genre")
#     company = request.args.get("company")

#     query = Movies.select()
#     if movie_name:
#         query = query.where(Movies.title ** movie_name)
#     if genre:
#         query = query.where(Movies.genre)
    



@app.before_request
def _db_connect():
    database.connect()


@app.teardown_request
def _db_close(_):
    if not database.is_closed():
        database.close()


@app.route('/')
def hello_world():
    return 'Hello, World!'


if __name__ == '__main__':
    # print("A")
    app.run()