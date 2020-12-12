from typing import Any, List
from datetime import datetime

import bcrypt
from flask import Flask, abort, render_template, request, session, url_for
from playhouse.shortcuts import model_to_dict
import peewee
from werkzeug.utils import redirect

from migrate_to_postgress import *

app = Flask(__name__)
app.config.from_pyfile('config.py')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.j2')
    if session.get('username') is not None:
        return render_template('search_movies.j2', 
            all_genres=get_all("genres"), 
            all_companies=get_all("companies"))
    salt = bcrypt.gensalt(prefix=b'2b', rounds=10)
    unhashed_password = request.form['password'].encode('utf-8')
    hashed_password = bcrypt.hashpw(unhashed_password, salt)
    fields = {
        **request.form,
        'password': hashed_password,
        'level': 1,
    }
    existing_names = Users.select(Users.username)
    existing_names = list(existing_names.dicts())
    existing_names = [d["username"] for d in existing_names]
    existing_emails = Users.select(Users.email)
    existing_emails = list(existing_emails.dicts())
    existing_emails = [d["email"] for d in existing_emails]
    if fields["username"] in existing_names:
        abort(422, f"This username is already occupied, please choose another.")
    if fields["email"] in existing_emails:
        abort(422, f"This email is already occupied, please choose another.")
    Users.create(**fields)
    user = Users.select().where(Users.username == fields["username"]).get()
    session['username'] = user.username
    session['user_id'] = user.id
    return render_template('search_movies.j2', 
            all_genres=get_all("genres"), 
            all_companies=get_all("companies"))


def get_all(table_name):
    table = get_table_class(table_name)
    entities = table.select()
    return entities


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.j2')
    if session.get('username') is not None:
        return render_template('search_movies.j2', 
            all_genres=get_all("genres"), 
            all_companies=get_all("companies"))
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
    session['user_id'] = user.id
    return render_template('search_movies.j2', 
            all_genres=get_all("genres"), 
            all_companies=get_all("companies"))

def isempty(x):
    if x == "":
        return None
    return int(x)

@app.route('/search_movies', methods=['GET', 'POST'])
def search_movies():
    if session.get('username') is None:
        return render_template('login.j2')
    if request.method == 'GET':
        return render_template('search_movies.j2', 
            all_genres=get_all("genres"), 
            all_companies=get_all("companies"))
    movie_name = request.form["movie_name"]
    genre = isempty(request.form["genre"])
    company = isempty(request.form["company"])
    query = Movies.select()
    if movie_name:
        query = query.where(Movies.title % f"%{movie_name}%")
        if not query.exists():
            title_movie_name = movie_name.title()
            query = Movies.select().where(Movies.title % f"%{title_movie_name}%")
    if genre:
        query = query.join(MoviesGenres, on=(Movies.id == MoviesGenres.movie_id)).where(MoviesGenres.genre_id == genre).select()
    if company:
        query = query.join(MoviesCompanies, on=(Movies.id == MoviesCompanies.movie_id)).where(MoviesCompanies.company_id == company).select()
    return render_template('search_movies.j2', display_movies=query,
                                            all_genres=get_all("genres"), 
                                            all_companies=get_all("companies"))

@app.route('/view_movie/<movie_id>')
def show_movie_page(movie_id: int) -> List[Any]:
    if session.get('username') is None:
        return render_template('login.j2')
    data =(Comments
                .select(Comments, Users.username)
                .join(Users)
                .where(Comments.movie_id == movie_id))
    comments = data.dicts()

    movies_g_c = (Movies
                    .select(
                        Movies.id.alias('id'),
                        peewee.fn.ARRAY_TO_STRING(
                            peewee.fn.ARRAY_AGG(peewee.fn.Distinct(Genres.name)), ', ',
                        ).alias('genres'),
                        peewee.fn.ARRAY_TO_STRING(
                            peewee.fn.ARRAY_AGG(peewee.fn.Distinct(Companies.name)), ', ',
                        ).alias('companies'),
                    )
                    .join(MoviesGenres, on=(MoviesGenres.movie_id == Movies.id))
                    .join(Genres, on=(MoviesGenres.genre_id == Genres.id))
                    .join(MoviesCompanies, on=(MoviesCompanies.movie_id == Movies.id))
                    .join(Companies, on=(MoviesCompanies.company_id == Companies.id))
                    .group_by(Movies.id)
                    .where(Movies.id == movie_id))
    
    movies_total = (
                    Movies
                    .select(Movies
                            ,movies_g_c.c.genres.alias("genres")
                            ,movies_g_c.c.companies.alias("companies")
                            )
                    .join(movies_g_c, on=(Movies.id == movies_g_c.c.id))
    )
    movies_total = movies_total.dicts()
    movie = movies_total[0]
    return render_template('movie.j2', movie=movie, comments=comments)


@app.route("/leave_comment/<movie_id>", methods=['POST'])
def leave_comment(movie_id: int):
    if session.get('username') is None:
        return render_template('login.j2')

    fields = {
        **request.form,
        'user_id': session['user_id'],
        'movie_id': movie_id,
        'time': datetime.now()
    }    
    Comments.create(**fields)
    query1 = Comments.select(
            peewee.fn.COUNT(Comments.stars), 
            peewee.fn.AVG(Comments.stars)).where(Comments.movie_id == movie_id)
    
    results = query1.get()
    vote_c = results.count
    vote_a = results.avg
    Movies.update(vote_count=vote_c, vote_average=vote_a).where(Movies.id == movie_id).execute()
    return redirect(url_for('show_movie_page', movie_id=movie_id))

@app.before_request
def _db_connect():
    database.connect()


@app.teardown_request
def _db_close(_):
    if not database.is_closed():
        database.close()


@app.route('/')
def hello_world():
    return redirect(url_for('login'))


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if session.get('username') is None:
        return render_template('login.j2')
    for session_value in ('username', 'user_id'):
        session.pop(session_value, None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run()