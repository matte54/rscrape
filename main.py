import datetime
import json
import os
import random
import re
import sys
import time
import humanize

import praw
import prawcore
import prawcore.exceptions
import requests

from credentials import CLIENTID, CLIENTSECRET, USERAGENT, USERNAME, PASSWORD

####VARIABLES TO TWEAK####
POSTLENGTH = 100  # accepted char length of posts. DEFAULT 100
UPVOTES = 1  # least number of upvotes needed DEFAULT 1
COMMENT_NUM = 3  # least comments to consider post DEFAULT 3
GET_NUM_COM = 40  # amount of comments to grab per cycle DEFAULT 30
ADD_POP_REDDITS = 10  # amount of popular reddits to add after first cycle DEFAULT 10
APITIME = 25  # seconds to wait between calls DEFAULT 30
LIMBOCYCLES = 5  # amount of cycles to leave out limbo subreddits. DEFAULT 2
LIMBOTRESHOLD = 10  # Minimum amount of entries found to put subreddit in limbo DEFAULT 3
#
SUBREDDITLIST = []
OG_SUBREDDITLIST = []
REMOVEDSRS = []
SAVEDIDS = []
IGNORELIST = []
LIMBO = {}  # changed to dictionary
run = True

# load subreddits
with open("./data/subreddits.txt", 'r', encoding='utf8') as f:
    lines = f.readlines()
    for line in lines:
        fixedline = line.strip("\n")
        SUBREDDITLIST.append(fixedline.lower())
        OG_SUBREDDITLIST.append(fixedline.lower())

# load ignorelist
with open("./data/ignorelist.txt", 'r', encoding='utf8') as igf:
    iglines = igf.readlines()
    for igline in iglines:
        igfixedline = igline.strip("\n")
        IGNORELIST.append(fixedline.lower())

# load stats file
try:
    with open("./stats/advstats.json", "r") as f:
        statsdata = json.load(f)
except FileNotFoundError:
    print(f'Statsfile not found...')

reddit = praw.Reddit(client_id=CLIENTID,
                     client_secret=CLIENTSECRET,
                     user_agent=USERAGENT,
                     username=USERNAME,
                     password=PASSWORD)
print("Authenticating...")
if reddit.user.me() == USERNAME:
    print(f"Successfully logged in as {USERNAME}!")
else:
    sys.exit('Authentication error')


def getpopreddits():
    srlist = []
    xr = reddit.subreddits
    for sr in xr.popular(limit=250):
        if sr.over18:
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


def getcomments(subreddit, amount, filterset=False):
    idlist = []
    subreddit = reddit.subreddit(subreddit)
    if filterset:
        use_filter = subreddit.new
        flag = "new"
    else:
        use_filter = subreddit.hot
        flag = "hot"
    print(f'Accessing {subreddit}({flag}) subreddit...')
    for post in use_filter(limit=amount):
        if post.stickied == False and post.over_18 == False and post.score >= UPVOTES and post.num_comments > COMMENT_NUM:
            local_id = post.id
            comment = post.comments
            if post.comments and local_id not in SAVEDIDS:
                idlist.append(local_id)
                SAVEDIDS.append(local_id)
    return idlist


def get_statement_and_answer(idlist):
    convos = []
    denied = 0
    for i in idlist:
        post = reddit.submission(id=i)
        post.comment_sort = "hot"
        post.comments.replace_more(limit=0)
        for comment in post.comments:
            answer = ""
            statement = ""
            if comment.stickied == False and comment.score >= UPVOTES and len(comment.body) < POSTLENGTH:
                statement = comment.body
                replies = comment.replies
                replies.comment_sort = "best"
                if len(replies) > 0:
                    if replies[0].score >= UPVOTES and len(replies[0].body) < POSTLENGTH:
                        answer = replies[0].body
            if answer != "":
                dirtydata = f"{statement} / {answer}"
                cleandata = cleanup(dirtydata)
                if cleandata != "":
                    convos.append(cleandata)
                else:
                    denied += 1
    if denied > 0:
        print(f'{denied} lines IGNORED by cleaning.')
        pass
    return convos


def write_data(data):
    writes = 0
    dupes = 0
    now = datetime.datetime.now()
    with open(f'./data/conversations_{now.year}_{now.month}.txt', 'a', encoding='utf8') as file:
        for i in data:
            with open(f'./data/conversations_{now.year}_{now.month}.txt', 'r', encoding='utf8') as fRead:
                if i in fRead.read():
                    #print(f'{i} already excists IGNORING!')
                    dupes += 1
                    pass
                else:
                    file.write(i)
                    file.write("\n")
                    writes += 1
    if writes > 0:
        #print(f'Wrote {writes} new lines')
        pass
    if dupes > 0:
        #print(f'Ignored {dupes} duplicate lines')
        pass
    return f"./data/conversations_{now.year}_{now.month}.txt", dupes, writes


# Cleaning up the strings and removing crap
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


def write_json(file_path, data):
    print(f'Saving stats to {file_path}!')
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)


# stats collection for finetuning.
def collect_stats(data, subreddit, writes, dupes):
    if subreddit in OG_SUBREDDITLIST:
        # for the default subreddits
        if subreddit in data["default"]:
            data["default"][subreddit]["writes"] += writes
            data["default"][subreddit]["dupes"] += dupes
        else:
            data["default"][subreddit] = {}
            data["default"][subreddit]["writes"] = writes
            data["default"][subreddit]["dupes"] = dupes
            if writes == 0:
                data["default"][subreddit][
                    "last_change"] = "0000-00-00"  # this is to make sure the key atleast gets entered.
        if writes > 0:
            date_only = str(datetime.datetime.now().date())
            data["default"][subreddit]["last_change"] = date_only
    else:
        # for added popular subreddits
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
    run_cycle = 1
    while run:
        #print('Loop running')
        try:
            cycle = 1
            totaldupes = 0
            totalwrites = 0
            print(f'Subreddits in limbo for this run: {LIMBO}')
            print(f'-----STARTING CYCLE {run_cycle}----')
            for current_subreddit in SUBREDDITLIST:
                print(f'Using entry {cycle}/{len(SUBREDDITLIST)}, limbo:{len(LIMBO)} cycle:{run_cycle}')
                idlist = getcomments(current_subreddit, GET_NUM_COM, filterflag)
                convolist = get_statement_and_answer(idlist)
                filename, dupes, writes = write_data(convolist)
                collect_stats(statsdata, current_subreddit, writes, dupes)  # stats collection
                totaldupes += dupes
                totalwrites += writes
                if writes < 3 and current_subreddit not in OG_SUBREDDITLIST:
                    # if less then 3 writes and its not a user added subreddit: remove
                    REMOVEDSRS.append(current_subreddit)
                    SUBREDDITLIST.remove(current_subreddit)
                    print(f'Removing popular subreddit {current_subreddit} from rotation')
                elif writes < LIMBOTRESHOLD:
                    SUBREDDITLIST.remove(current_subreddit)
                    LIMBO[current_subreddit] = LIMBOCYCLES  # Add the subreddit to limbo for some cycles
                    print(f'Adding "{current_subreddit}" to limbo (threshold {LIMBOTRESHOLD})')
                filesize = os.stat(filename).st_size
                print(f'Writes: {totalwrites} - {filename[7:]} now {humanize.naturalsize(filesize)}')
                #print(f'API Friendly wait...{APITIME}s')
                time.sleep(APITIME)
                cycle += 1
                print("-------------------------")
            # disabled for now.
            # if TOTALWRITES < 100:
            #    SAVEDIDS.clear()
            #    SUBREDDITLIST.clear()
            #    srs = getPopreddits()
            # if this low find rate clear all lists and repopulate.
            if totalwrites < 100 and filterflag == False:
                print(f'Switching to NEW for one cycle...')
                filterflag = True
                # change to new for one cycle
            else:
                filterflag = False
            print(f'DUPES/WRITES WAS {totaldupes}/{totalwrites}')
            SAVEDIDS.clear()
            srs = getpopreddits()
            write_json("./stats/advstats.json", statsdata)  # write stats to json file
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
            # show_limbo()
            run_cycle += 1
            print("-------------------------")

        except prawcore.exceptions.ServerError as e:
            print(e)
            time.sleep(60)
            print('Error, Retrying...')
        except prawcore.exceptions.RequestException as e:
            print(e)
            time.sleep(60)
            print('Error, Retrying...')
        except requests.exceptions.ReadTimeout as e:
            print(e)
            time.sleep(60)
            print('Error, Retrying...')
        except prawcore.exceptions.Forbidden as e:
            print(f'403 Forbidden, removing subreddit "{current_subreddit}" from rotation.')
            SUBREDDITLIST.remove(current_subreddit)
            time.sleep(60)
            continue


if __name__ == "__main__":
    main()
