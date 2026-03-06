import ssl
import nltk

try:
    _create_unverified_https_context = ssl._create_unverified_context
    ssl._create_default_https_context = _create_unverified_https_context
except:
    pass

nltk.download("wordnet")
nltk.download("omw-1.4")
