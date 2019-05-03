import io
import os
import urllib.request
import requests
import re
import string
import timeit

from concurrent.futures import ThreadPoolExecutor
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types

from tkinter import *
from PIL import ImageTk, Image

from moviepy.editor import *

detectSpeech = True
downloadImages = False
selectImages = True
generateVideo = True

autoSelectImages = False

words = []

segmentLen = 59
segmentCount = 0
time = 0
audio = AudioFileClip("input.mp3")
while time + 59 < audio.duration:
    segment = audio.subclip(time, time + segmentLen)
    segment.write_audiofile("segment-" + str(segmentCount) + ".wav", nbytes=2,
                            codec="pcm_s16le", bitrate="48k", ffmpeg_params=["-ac", "1"])
    time += segmentLen
    segmentCount += 1
audio = audio.subclip(time)
audio.write_audiofile("segment-" + str(segmentCount) + ".wav", nbytes=2,
                      codec="pcm_s16le", bitrate="48k", ffmpeg_params=["-ac", "1"])

if detectSpeech:
    for segmentIndex in range(0, segmentCount + 1):
        client = speech.SpeechClient()
        file_name = os.path.join(
            os.path.dirname(__file__),
            'resources',
            'audio.raw')

        with open("segment-" + str(segmentIndex) + ".wav", "rb") as audio_file:
            content = audio_file.read()
            audio = types.RecognitionAudio(content=content)

        config = types.RecognitionConfig(
            encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=44100,
            language_code='en-US',
            enable_word_time_offsets=True,
        )

        response = client.recognize(config, audio)
        for result in response.results:
            for word in result.alternatives[0].words:
                time = word.start_time.seconds + word.start_time.nanos * \
                    1e-9 + (segmentLen * segmentIndex)
                words.append((word.word.translate(
                    str.maketrans('', '', string.punctuation)), time))

print(words)
if len(words) == 0:
    words = [("test", 1), ("hello", 5)]

def downloadImage(word):
    print("Getting images for '" + word + "'")
    search = requests.get(
        "https://www.googleapis.com/customsearch/v1?cx=018141146439312972952:wmgyowf391i&key=" + apiKey + "&searchType=image&q=" + word).json()
    index = 0
    called = 0
    for item in search["items"]:
        link = item["link"]
        if link.endswith(".png") or link.endswith(".jpg"):
            called += 1
            fileName = "staging/" + word + "-" + \
                str(index) + (".png" if link.endswith(".png") else ".jpg")
            try:
                urllib.request.urlretrieve(link, fileName)
                image = Image.open(fileName)
                startingSize = image.size
                ratio = min(
                    1920 / startingSize[0], 1080 / startingSize[1])
                size = tuple([int(x * ratio)
                              for x in startingSize])
                image = image.resize(size, Image.ANTIALIAS)
                resized = Image.new("RGB", (1920, 1080))
                resized.paste(image, ((1920 - size[0]) // 2,
                                      (1080 - size[1]) // 2))
                resized.save(fileName)
                index += 1
            except Exception as e:
                print(e)
                continue
    print("Zero called for '" + word + "'!")


while True:
    try:
        if downloadImages:
            done = []
            toDownload = []
            for word in words:
                word = word[0]
                word = word.lower()
                if os.path.isfile("images/" + word + ".png") or os.path.isfile("images/" + word + ".jpg"):
                    continue
                if os.path.isfile("staging/" + word + "-0.png") or os.path.isfile("staging/" + word + "-0.jpg"):
                    continue
                if word in done:
                    continue
                toDownload.append(word)
                done.append(word)
            with ThreadPoolExecutor(max_workers=8) as executor:
                for word in toDownload:
                    executor.submit(downloadImage, (word))
                executor.shutdown(wait=True)

        def clickedImage(name, fileName):
            nameSansNumber = fileName.rpartition("-")[0]
            finalName = "images/" + nameSansNumber + \
                (".png" if fileName .endswith(".png") else ".jpg")
            os.rename("staging/" + fileName, finalName)
            for fileInDir in os.listdir("staging/"):
                if fileInDir.startswith(nameSansNumber):
                    os.remove("staging/" + fileInDir)
            root.destroy()

        if selectImages:
            imgsDoNotGc = []
            uniqueNames = {}
            for fileName in os.listdir("staging/"):
                nameSansNumber = fileName.rpartition("-")[0]
                if nameSansNumber not in uniqueNames:
                    uniqueNames[nameSansNumber] = []
                uniqueNames[nameSansNumber].append(fileName)
            for name, fileNames in uniqueNames.items():
                root = Tk()
                for fileName in fileNames:
                    try:
                        image = Image.open("staging/" + fileName)
                        image = image.resize((192, 108), Image.ANTIALIAS)
                        img = ImageTk.PhotoImage(image)
                        imgsDoNotGc.append(img)
                        label = Label(root, image=img)
                        label.bind("<Button-1>", lambda n, name=name,
                                   fileName=fileName: clickedImage(name, fileName))
                        label.pack()
                    except Exception as w:
                        print(w)
                root.mainloop()

        if autoSelectImages:
            for fileName in os.listdir("staging/"):
                name = fileName.rpartition(".")[0]
                if name.endswith("-0"):
                    nameSansNumber = fileName.rpartition("-")[0]
                    finalName = "images/" + nameSansNumber + \
                        (".png" if fileName.endswith(".png") else ".jpg")
                    os.rename("staging/" + fileName, finalName)
                    for fileInDir in os.listdir("staging/"):
                        if fileInDir.startswith(nameSansNumber):
                            os.remove("staging/" + fileInDir)

        #for index in range(len(words)):
        #    word = words[index][0].lower()
        #    if not (os.path.isfile("images/" + word + ".png") and os.path.isfile("images/" + word + ".png")):
        #        raise Exception("Missing image! " + word)

        break
    except Exception as e:
        print(e)
        print("Error selecting images, probably a failed download. Try again?")
        choice = input("Select: ")
        if choice == "break":
            break

if generateVideo:
    finalTime = words[-1][1] + 5
    base = ColorClip(size=(1920, 1080), color=[0, 0, 0])
    base = base.set_duration(finalTime, change_end=True)
    clips = [base]
    for index in range(len(words)):
        word = words[index]
        startTime = word[1]
        duration = 5
        if index + 1 < len(words):
            duration = words[index + 1][1] - startTime
        fileName = word[0].lower()
        fileName = "images/" + fileName + \
            ".png" if os.path.isfile(
                "images/" + fileName + ".png") else "images/" + fileName + ".jpg"
        if os.path.isfile(fileName):
            clip = ImageClip(fileName, duration=duration).set_start(startTime)
            clips.append(clip)
        else:
            print("Missing image '" + fileName + "'")
    base = CompositeVideoClip(
        clips, size=(1920, 1080), bg_color=[0, 0, 0])
    audio = AudioFileClip("input.mp3")
    base = base.set_audio(audio)
    base.write_videofile("output.mp4", fps=30)
