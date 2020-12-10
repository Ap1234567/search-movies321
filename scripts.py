from migrate_to_postgress import Genres, Companies, Movies, Users, MoviesGenres, MoviesCompanies, Comments


TABLES = [
    Genres, Companies, Movies, Users,
    MoviesGenres, MoviesCompanies, Comments
]


def get_table_class(table_name):
    name = table_name.title()
    tables = (t for t in TABLES if t.__name__ == name)
    return next(tables, None)