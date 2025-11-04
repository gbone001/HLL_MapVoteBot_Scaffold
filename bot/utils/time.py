from datetime import datetime
import pytz

# TODO This should not only work in one timezone.
def sydney_now():
    return datetime.now(pytz.timezone("Australia/Sydney"))

def fmt_end(dtobj):
    return dtobj.strftime("%Y-%m-%d %H:%M %Z")
