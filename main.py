import praw
import re
import sys
import datetime, time
import random
import os
import json
from humanize import naturalsize
from credentials import CLIENTID, CLIENTSECRET, USERAGENT, USERNAME, PASSWORD

####VARIABLES TO TWEAK####
POSTLENGTH = 100 #accepted char length of posts. DEFAULT 100
UPVOTES = 1 #least number of upvotes needed DEFAULT 1
COMMENT_NUM = 3 #least comments to consider post DEFAULT 3
GET_NUM_COM = 40 #amount of comments to grab per cycle DEFAULT 30
ADD_POP_REDDITS = 10 #amount of popular reddits to add after first cycle DEFAULT 10
APITIME = 25 #seconds to wait between calls DEFAULT 30
LIMBOCYCLES = 5 #amount of cycles to leave out limbo subreddits. DEFAULT 2
LIMBOTRESHOLD = 10 #Minimum amount of entries found to put subreddit in limbo DEFAULT 3
#
SUBREDDITLIST = []
OG_SUBREDDITLIST = []
REMOVEDSRS = []
SAVEDIDS = []
IGNORELIST = []
LIMBO = {} # changed to dictionary
run = True

#load subreddits
with open("./data/subreddits.txt", 'r', encoding='utf8') as f:
    lines = f.readlines()
    for line in lines:
        fixedline = line.strip("\n")
        SUBREDDITLIST.append(fixedline.lower())
        OG_SUBREDDITLIST.append(fixedline.lower())
f.close()

#load ignorelist
with open("./data/ignorelist.txt", 'r', encoding='utf8') as igf:
    iglines = igf.readlines()
    for igline in iglines:
        igfixedline = igline.strip("\n")
        IGNORELIST.append(fixedline.lower())
igf.close()

#load stats file
try:
    with open("./stats/advstats.json", "r") as f:
        statsdata = json.load(f)
except FileNotFoundError:
    print(f'{filePath} not found...')
f.close()


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

def getPopreddits():
    srlist = []
    xr = reddit.subreddits
    for sr in xr.popular(limit=250):
        if sr.over18 == True:
            continue
        sr = str(sr).lower()
        if sr in IGNORELIST:
            continue
        if sr not in SUBREDDITLIST and sr not in LIMBO and sr not in REMOVEDSRS:
            SUBREDDITLIST.append(str(sr).lower())
            srlist.append(str(sr).lower())
            if len(srlist) > ADD_POP_REDDITS:
                break
    random.shuffle(SUBREDDITLIST)
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

# show whats in limbo for debug
def show_limbo():
    if LIMBO:
        print('========= LIMBO =========')
        for sr, cycles in LIMBO.items():
            print(f'{sr} for {cycles} cycles')
    else:
        print('Nothing to see here...')

def writeJSON(filePath, data):
    print(f'Saving stats to {filePath}!')
    with open(filePath, "w") as f:
        json.dump(data, f, indent=4)
        f.close()
#stats collection for finetuning.
def collect_stats(data ,subreddit, writes, dupes):
    if subreddit in OG_SUBREDDITLIST:
        #for the default subreddits
        if subreddit in data["default"]:
            data["default"][subreddit]["writes"] += writes
            data["default"][subreddit]["dupes"] += dupes
        else:
            data["default"][subreddit] = {}
            data["default"][subreddit]["writes"] = writes
            data["default"][subreddit]["dupes"] = dupes
            if writes == 0:
                data["default"][subreddit]["last_change"] = "0000-00-00" #this is to make sure the key atleast gets entered.
        if writes > 0:
            date_only = str(datetime.datetime.now().date())
            data["default"][subreddit]["last_change"] = date_only
    else:
        #for added popular subreddits
        if subreddit in data["popular"]:
            data["popular"][subreddit]["writes"] += writes
            data["popular"][subreddit]["dupes"] += dupes
        else:
            data["popular"][subreddit] = {}
            data["popular"][subreddit]["writes"] = writes
            data["popular"][subreddit]["dupes"] = dupes
            if writes == 0:
                data["popular"][subreddit]["last_change"] = "0000-00-00"
        if writes > 0:
            date_only = str(datetime.datetime.now().date())
            data["popular"][subreddit]["last_change"] = date_only

def main():
    filterflag = False
    RUN_CYCLE = 1
    while run:
        try:
            CYCLE = 1
            TOTALDUPES = 0
            TOTALWRITES = 0
            #print(f'Subreddits in limbo for this run: {LIMBO}')
            print(f'-----STARTING CYCLE {RUN_CYCLE}----')
            for x in SUBREDDITLIST:
                print(f'Using entry {CYCLE}/{len(SUBREDDITLIST)}, limbo:{len(LIMBO)} cycle:{RUN_CYCLE}')
                idlist = getComments(x, GET_NUM_COM, filterflag)
                convolist = getStatementAndAnswer(idlist)
                filename, DUPES, WRITES = writeData(convolist)
                collect_stats(statsdata, x, WRITES, DUPES) #stats collection
                TOTALDUPES += DUPES
                TOTALWRITES += WRITES
                if WRITES < 3 and x not in OG_SUBREDDITLIST:
                    #if less then 3 writes and its not a user added subreddit: remove
                    REMOVEDSRS.append(x)
                    SUBREDDITLIST.remove(x)
                    print(f'Removing popular subreddit {x} from rotation')
                elif WRITES < LIMBOTRESHOLD:
                    SUBREDDITLIST.remove(x)
                    LIMBO[x] = LIMBOCYCLES # Add the subreddit to limbo for some cycles
                    print(f'Adding "{x}" to limbo (threshold {LIMBOTRESHOLD})')
                filesize = os.stat(filename).st_size
                print(f'{filename[7:]} now {naturalsize(filesize)}')
                print(f'Total writes this cycle: {TOTALWRITES}')
                print(f'API Friendly wait...{APITIME}s')
                time.sleep(APITIME)
                CYCLE += 1
                print("-------------------------")
            #disabled for now.
            #if TOTALWRITES < 100:
            #    SAVEDIDS.clear()
            #    SUBREDDITLIST.clear()
            #    srs = getPopreddits()
                #if this low find rate clear all lists and repopulate.
            if TOTALWRITES < 100 and filterflag == False:
                print(f'Switching to NEW for one cycle...')
                filterflag = True
                #change to new for one cycle
            else:
                filterflag = False
            #print(f'DUPES/WRITES WAS {TOTALDUPES}/{TOTALWRITES}')
            SAVEDIDS.clear()
            srs = getPopreddits()
            writeJSON("./stats/advstats.json", statsdata) #write stats to json file
            print(f'Adding {ADD_POP_REDDITS} popular subreddits...')
            for y in srs:
                print(y)
            print("-------------------------")

            # if there's anything in limbo decrement its time by one
            if LIMBO:
                for sr in LIMBO:
                    LIMBO[sr] -= 1
                # get any subreddit that has 0 cycles left in limbo
                remove = [sr for sr in LIMBO if LIMBO[sr] < 1]
                # remove the subreddit from limbo and add it back into the subreddit list
                for sr in remove:
                    print(f'Taking "{sr}" out of limbo...')
                    del LIMBO[sr]
                    SUBREDDITLIST.append(sr)
            #show_limbo()
            RUN_CYCLE += 1
            print("-------------------------")

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
