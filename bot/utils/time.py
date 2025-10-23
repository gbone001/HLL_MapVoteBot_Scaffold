
from datetime import datetime
import pytz

def sydney_now():
    return datetime.now(pytz.timezone("Australia/Sydney"))

def fmt_end(dtobj):
    return dtobj.strftime("%Y-%m-%d %H:%M %Z")
