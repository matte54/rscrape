import praw
import re
import sys
import tqdm
import datetime, time
import random
import os
from humanize import naturalsize
from credentials import CLIENTID, CLIENTSECRET, USERAGENT, USERNAME, PASSWORD

SUBREDDITLIST = []
with open("./data/subreddits.txt", 'r', encoding='utf8') as f:
    lines = f.readlines()
    for line in lines:
        fixedline = line.strip("\n")
        SUBREDDITLIST.append(fixedline)


SAVEDIDS = []

def convertUTC(utc):
    x = datetime.utcfromtimestamp(utc)
    return x

run = True

reddit = praw.Reddit(client_id = CLIENTID, \
                     client_secret = CLIENTSECRET, \
                     user_agent = USERAGENT, \
                     username = USERNAME, \
                     password = PASSWORD)
print("Authenticating...")
if reddit.user.me() == USERNAME:
    print(f"Successfully logged in as {USERNAME}!")
else:
    sys.exit('Authentication error')


def getPopreddits(amount=10):
    srlist = []
    xr = reddit.subreddits
    for sr in xr.popular(limit=amount):
        if sr not in SUBREDDITLIST:
            SUBREDDITLIST.append(str(sr))
            srlist.append(str(sr))
    return srlist


def getComments(subReddit, amount):
    idlist = []
    subreddit = reddit.subreddit(subReddit)
    print(f'Accessing {subReddit} subreddit...')
    for post in subreddit.hot(limit=amount):
        if post.stickied == False and post.over_18 == False and post.score >= 1 and post.num_comments > 3:
            id = post.id
            comment = post.comments
            if post.comments and id not in SAVEDIDS:
                idlist.append(id)
                SAVEDIDS.append(id)
    return(idlist)

def getStatementAndAnswer(idlist):
    convos = []
    for i in idlist:
        post = reddit.submission(id=i)
        post.comment_sort = "hot"
        post.comments.replace_more(limit=0)
        for comment in post.comments:
            ANSWER = ""
            STATEMENT = ""
            if comment.stickied == False and comment.score >= 1 and len(comment.body) < 50:
                STATEMENT = comment.body
                replies = comment.replies
                replies.comment_sort = "best"
                if len(replies) > 0:
                    if replies[0].score >= 1 and len(replies[0].body) < 50:
                        ANSWER = replies[0].body
            if ANSWER != "":
                dirtydata = f"{STATEMENT} / {ANSWER}"
                cleandata = cleanup(dirtydata)
                if cleandata != "":
                    convos.append(cleandata)
    return convos

def writeData(data):
    WRITES = 0
    DUPES = 0
    now = datetime.datetime.now()
    with open(f'./data/conversations_{now.month}.txt', 'a', encoding='utf8') as f:
        for i in data:
            with open(f'./data/conversations_{now.month}.txt', 'r', encoding='utf8') as fRead:
                if i in fRead.read():
                    #print(f'{i} already excists IGNORING!')
                    DUPES += 1
                    pass
                else:
                    f.write(i)
                    f.write("\n\n")
                    WRITES += 1
    if WRITES > 0:
        print(f'Wrote {WRITES} new lines')
    if DUPES > 0:
        print(f'Ignored {DUPES} duplicate lines')
    return f"./data/conversations_{now.month}.txt"


#Cleaning up the strings and removing crap
badwords = ["[removed]", "r/", "/r/", "edit:", "/u/", "u/", "\n", "[deleted]", "![", "http"]
def cleanup(string):
    DENIED = 0
    no = re.search(r'^(http|<?https?:\S+)|^\s|^\W|^\d+$|^\d|^\s*$', string)
    if no:
        #print(f'{string} DENIED BY CLEANUP! (REGEX)')
        DENIED += 1
        return ""
    if " / " not in string:
        #print(f'{string} DENIED BY CLEANUP! (NO DASH)')
        DENIED += 1
        return ""
    for i in badwords:
        if i in string:
            #print(f'{string} DENIED BY CLEANUP!(BAD WORD {i})')
            DENIED += 1
            return ""
    if DENIED > 0:
        print(f'Cleanup removed {DENIED} strings.')

    return string


def main():
    srs = getPopreddits()
    print(f'Adding... {srs}')
    while run:
        for x in SUBREDDITLIST:
            #x = random.choice(SUBREDDITLIST)
            idlist = getComments(x, 25)
            convolist = getStatementAndAnswer(idlist)
            filename = writeData(convolist)
            filesize = os.stat(filename).st_size
            print(f'{filename[7:]} now {naturalsize(filesize)}')
            print(f"API Friendly wait...30s")
            time.sleep(30)
            print("-------------------------")
        SAVEDIDS = []
        srs = getPopreddits(30)
        print(f'Adding... {srs}')

if __name__ == "__main__":
    main()
