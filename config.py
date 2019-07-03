# Statement for enabling the development environment
DEBUG = True

# Define the application directory
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = '/home/ishark/eraFA/static'
ALLOWED_EXTENSIONS = set(['jpg'])

# Define the database - we are working with
SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
    username="erafa",
    password="SydJM9N5Hh",
    hostname="erafa.mysql.pythonanywhere-services.com",
    databasename="erafa$data",
)
SQLALCHEMY_POOL_RECYCLE = 299
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Application threads. A common general assumption is
# using 2 per available processor cores - to handle
# incoming requests using one and performing background
# operations using the other.
#THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)*
CSRF_ENABLED     = True

# Use a secure, unique and absolutely secret key for
# signing the data.
CSRF_SESSION_KEY = "UxpmmSlQmjKRPdOb7RGY"

# Secret key for signing cookies
SECRET_KEY = "ubQYX3N7RBs1VB1REXrQ"
