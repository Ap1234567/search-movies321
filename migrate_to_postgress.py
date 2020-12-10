from peewee import (
    DateField, FloatField, IntegerField, Model,
    PostgresqlDatabase, TextField,
)

from datetime import datetime
import json
import pandas as pd

database = PostgresqlDatabase(
    "d85ja4vg37fta1",
    user="nxzgsjauliebsa",
    password="348754ddd23415566ae37bf28c29030671330a926c4a0a686ef8fba2601b7147",
    host="ec2-35-169-184-61.compute-1.amazonaws.com",
    port=5432,
)

class UnknownField(object):
    def __init__(self, *_, **__):
        pass


class BaseModel(Model):
    class Meta:
        database = database

        
class Genres(BaseModel):
    id = IntegerField(unique=True)
    name = TextField()

    class Meta:
        table_name = 'genres'        
        

class Companies(BaseModel):
    id = IntegerField(unique=True)
    name = TextField()

    class Meta:
        table_name = 'companies'

class Movies(BaseModel):
    id = IntegerField(unique=True)
    title = TextField()
    budget = IntegerField(null=True)
    overview = TextField(null=True)
    release_date = DateField(null=True)
    revenue = IntegerField(null=True)
    runtime = IntegerField(null=True)
    tagline = TextField(null=True)
    poster = TextField(null=True)
    vote_average = FloatField()
    vote_count = IntegerField()

    class Meta:
        table_name = 'movies'


class Users(BaseModel):
    username = TextField(unique=True)
    password = TextField()
    email = TextField(unique=True)
    birthday = DateField()
    level = IntegerField()

    class Meta:
        table_name = 'users'


class MoviesGenres(BaseModel):
    movie_id = IntegerField()
    genre_id = IntegerField()

    class Meta:
        table_name = 'movies_genres'


class MoviesCompanies(BaseModel):
    movie_id = IntegerField()
    company_id = IntegerField()

    class Meta:
        table_name = 'movies_companies'        

class Comments(BaseModel):
    movie_id = IntegerField()
    user_id = IntegerField()
    content = TextField()
    stars = IntegerField()
    time = DateField()


TABLES = [
    Genres, Companies, Movies, Users,
    MoviesGenres, MoviesCompanies, Comments
]

# with database.connection_context():
#     database.create_tables(TABLES, safe=True)
#     database.commit()

def get_poster(movie):
    location = "https://image.tmdb.org/t/p/original" 
    if movie["poster_path"] is not None:
        return location + movie["poster_path"]
    elif movie["backdrop_path"] is not None:
        return location + movie["backdrop_path"]
    else:
        return None

def set_dates(date):
    if type(date) != str or date == "":
        return None
    elif '/' in date:
        return datetime.strptime(date, '%d/%m/%Y')
    elif '-' in date:
        return datetime.strptime(date, '%Y-%m-%d')
    else:
        return None
    
def set_movies_data():
    path = 'data/movies_metadata.csv'
    movies = pd.read_csv(path, low_memory=False)

    cols = ["id", "title", "belongs_to_collection", "budget", "genres", 
            "overview", "production_companies",
        "release_date", "revenue", "runtime", "tagline", ]#"production_countries",
    movies = movies[cols]

    movies = movies.loc[movies.belongs_to_collection.notnull()]

    list_cols = ["genres", "production_companies"] # ,"production_countries"
    for col in list_cols:
        movies = movies[movies[col].str.contains("{") == True]
        movies[col] = movies[col].apply(lambda x: list(eval(x)))
        
    movies["belongs_to_collection"] = movies["belongs_to_collection"].apply(lambda x: eval(x))   
    movies["poster"] = movies["belongs_to_collection"].apply(lambda x: get_poster(x))
    movies = movies.loc[movies.poster.notnull()]
    movies.drop("belongs_to_collection", axis='columns', inplace=True)
                                            
    movies["release_date"] = movies["release_date"].apply(lambda x: set_dates(x))

    movies["id"] = movies["id"].astype(int)
    movies["budget"] = movies["budget"].astype(float)
    movies["revenue"] = movies["revenue"].astype(int)

    movies.replace({pd.NaT: None}, inplace=True)

    return movies


def json_to_table(movies, column_name): 
    entities = {}
    entitities_values = set()
    for line in movies[column_name]:
        for x in line:
            key = x["id"]
            value = x["name"]
            if value not in entitities_values:
                entitities_values.add(value)
                entities[key] = value
    return entities     
    
def relative_data(movies, col):
    data = []
    for i, movie in movies.iterrows():
        movie_id = int(movie.id)
        for z in movie[col]:
            data.append((movie_id, z["id"]))
    return data



def to_peewee_compatible(parsed_json):
    return [
        {"id": key, 'name': value}
        for key, value
        in parsed_json.items()
    ]

def get_all_from_table(table):
    for category in table.select():
        print(category)



def insert_parsed_json(db, parsed_json, table_name):
    to_insert = to_peewee_compatible(parsed_json)
    table = get_table_class(table_name)
    table.insert_many(to_insert).on_conflict_ignore().execute()
    db.commit()


class NoSuchTableException(Exception):
    pass

def get_table_class(table_name):
    for t in TABLES:
        if t.__name__ == table_name.title():
            return t

    raise NoSuchTableException()


def insert_movies(database, movies):
    movies["vote_average"] = 0
    movies["vote_count"] = 0
    cols = ["id", "title", "budget", "overview", "release_date",
            "revenue", "runtime", "tagline", "poster", "vote_average",
        "vote_count"]
    table = get_table_class("movies")
    to_insert_movies = movies[cols].to_dict('records')
    table.insert_many(to_insert_movies).on_conflict_ignore().execute()
    database.commit()


def insert_to_side_tables(movies):
    genres = json_to_table(movies, "genres")
    companies = json_to_table(movies, "production_companies")

    insert_parsed_json(database, genres, "genres")
    insert_parsed_json(database, companies, "companies")


def insert_to_relative_tables(movies):
    movies_genres = relative_data(movies, "genres")
    movies_companies = relative_data(movies, "production_companies")


    parsed_movies_genres = [{"movie_id": x, "genre_id": y} for x, y in movies_genres]
    parsed_movies_companies = [{"movie_id": x, "company_id": y} for x, y in movies_companies]

    insert_rules = [
        (MoviesCompanies, parsed_movies_companies),
        (MoviesGenres, parsed_movies_genres),
    ]

    for table, entities in insert_rules:
        table.insert_many(entities).on_conflict_ignore().execute()
    database.commit()

def main():
    movies = set_movies_data()
    insert_movies(database, movies)
    insert_to_side_tables(movies)
    insert_to_relative_tables(movies)
