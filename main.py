import praw
import re
import sys
import datetime, time
import random
import os
from humanize import naturalsize
from credentials import CLIENTID, CLIENTSECRET, USERAGENT, USERNAME, PASSWORD

####VARIABLES TO TWEAK####
POSTLENGTH = 100 #accepted char length of posts. DEFAULT 100
UPVOTES = 1 #least number of upvotes needed DEFAULT 1
COMMENT_NUM = 3 #least comments to consider post DEFAULT 3
GET_NUM_COM = 40 #amount of comments to grab per cycle DEFAULT 30
ADD_POP_REDDITS = 50 #amount of popular reddits to add after first cycle DEFAULT 40
APITIME = 25 #seconds to wait between calls DEFAULT 30
LIMBOCYCLES = 3 #amount of cycles to leave out limbo subreddits. DEFAULT 2
#
SUBREDDITLIST = []
SAVEDIDS = []
LIMBO = []
LIMBOTIME = 0
run = True

with open("./data/subreddits.txt", 'r', encoding='utf8') as f:
    lines = f.readlines()
    for line in lines:
        fixedline = line.strip("\n")
        SUBREDDITLIST.append(fixedline.lower())

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

def getPopreddits(amount=25):
    srlist = []
    xr = reddit.subreddits
    for sr in xr.popular(limit=amount):
        if sr not in SUBREDDITLIST:
            SUBREDDITLIST.append(str(sr).lower())
            random.shuffle(SUBREDDITLIST)
            srlist.append(str(sr))
    return srlist

def getComments(subReddit, amount, filterSet = False):
    idlist = []
    subreddit = reddit.subreddit(subReddit)
    if filterSet == True:
        filter = subreddit.new
        flag = "new"
    else:
        filter = subreddit.hot
        flag = "hot"
    print(f'Accessing {subReddit}({flag}) subreddit...')
    for post in filter(limit=amount):
        if post.stickied == False and post.over_18 == False and post.score >= UPVOTES and post.num_comments > COMMENT_NUM:
            id = post.id
            comment = post.comments
            if post.comments and id not in SAVEDIDS:
                idlist.append(id)
                SAVEDIDS.append(id)
    return(idlist)

def getStatementAndAnswer(idlist):
    convos = []
    DENIED = 0
    for i in idlist:
        post = reddit.submission(id=i)
        post.comment_sort = "hot"
        post.comments.replace_more(limit=0)
        for comment in post.comments:
            ANSWER = ""
            STATEMENT = ""
            if comment.stickied == False and comment.score >= UPVOTES and len(comment.body) < POSTLENGTH:
                STATEMENT = comment.body
                replies = comment.replies
                replies.comment_sort = "best"
                if len(replies) > 0:
                    if replies[0].score >= UPVOTES and len(replies[0].body) < POSTLENGTH:
                        ANSWER = replies[0].body
            if ANSWER != "":
                dirtydata = f"{STATEMENT} / {ANSWER}"
                cleandata = cleanup(dirtydata)
                if cleandata != "":
                    convos.append(cleandata)
                else:
                    DENIED += 1
    if DENIED > 0:
        print(f'{DENIED} lines IGNORED by cleaning.')
    return convos

def writeData(data):
    WRITES = 0
    DUPES = 0
    now = datetime.datetime.now()
    with open(f'./data/conversations_{now.year}_{now.month}.txt', 'a', encoding='utf8') as f:
        for i in data:
            with open(f'./data/conversations_{now.year}_{now.month}.txt', 'r', encoding='utf8') as fRead:
                if i in fRead.read():
                    #print(f'{i} already excists IGNORING!')
                    DUPES += 1
                    pass
                else:
                    f.write(i)
                    f.write("\n")
                    WRITES += 1
    if WRITES > 0:
        print(f'Wrote {WRITES} new lines')
    if DUPES > 0:
        print(f'Ignored {DUPES} duplicate lines')
    return f"./data/conversations_{now.year}_{now.month}.txt", DUPES, WRITES

#Cleaning up the strings and removing crap
badwords = ["[removed]", "r/", "/r/", "edit:", "/u/", "u/", "\n", "[deleted]", "![", "http"]
def cleanup(string):
    no = re.search(r'^(http|<?https?:\S+)|^\s|^\W|^\d+$|^\d|^\s*$', string)
    if no:
        #print(f'{string} DENIED BY CLEANUP! (REGEX)')
        return ""
    if " / " not in string:
        #print(f'{string} DENIED BY CLEANUP! (NO DASH)')
        return ""
    for i in badwords:
        if i in string:
            #print(f'{string} DENIED BY CLEANUP!(BAD WORD {i})')
            return ""
    return string

def main():
    filterflag = False
    while run:
        try:
            CYCLE = 1
            TOTALDUPES = 0
            TOTALWRITES = 0
            print(f'Subreddits in limbo for this run: {LIMBO}')
            for x in SUBREDDITLIST:
                print(f'Using entry {CYCLE}/{len(SUBREDDITLIST)}')
                idlist = getComments(x, GET_NUM_COM, filterflag)
                convolist = getStatementAndAnswer(idlist)
                filename, DUPES, WRITES = writeData(convolist)
                TOTALDUPES += DUPES
                TOTALWRITES += WRITES
                if WRITES < 3:
                    SUBREDDITLIST.remove(x)
                    LIMBO.append(x)
                    print(f'Temporary putting "{x}" in limbo (not enough new entries)')
                filesize = os.stat(filename).st_size
                print(f'{filename[7:]} now {naturalsize(filesize)}')
                print(f'Total writes this cycle:{TOTALWRITES}')
                print(f"API Friendly wait...{APITIME}s")
                time.sleep(APITIME)
                CYCLE += 1
                print("-------------------------")
            if TOTALWRITES < 100:
                SAVEDIDS.clear()
                SUBREDDITLIST.clear()
                srs = getPopreddits(50)
                #if this low find rate clear all lists and repopulate.
            if TOTALDUPES > (TOTALWRITES * 2) and filterflag == False:
                filterflag = True
                #change to new for one cycle
            else:
                filterflag = False
            print(f'WRITES/DUPES WAS {TOTALWRITES}/{TOTALDUPES}')
            SAVEDIDS.clear()
            srs = getPopreddits(ADD_POP_REDDITS)
            print(f'Adding... {srs}')
            LIMBOTIME += 1
            if LIMBOTIME == LIMBOCYCLES:
                print(f'Removing {LIMBO} from limbo.')
                SUBREDDITLIST.extend(LIMBO)
                del LIMBO[:]
                LIMBOTIME = 0

        except prawcore.exceptions.ServerError as e:
            print(e)
            time.sleep(60)
            print('Retrying...')
        except prawcore.exceptions.RequestException as e:
            print(e)
            time.sleep(60)
            print('Retrying...')
        except requests.exceptions.ReadTimeout as e:
            print(e)
            time.sleep(60)
            print('Retrying...')

if __name__ == "__main__":
    main()
