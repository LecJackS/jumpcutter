from contextlib import closing
from PIL import Image
import subprocess
from audiotsm import phasevocoder
from audiotsm.io.wav import WavReader, WavWriter
from scipy.io import wavfile
import numpy as np
import re
import math
from shutil import copyfile, rmtree
import os
import argparse
from pytube import YouTube


def downloadFile(url):
    name = YouTube(url).streams.first().download()
    newname = name.replace(' ','_')
    os.rename(name,newname)
    return newname

def getMaxVolume(s):
    maxv = float(np.max(s))
    minv = float(np.min(s))
    return max(maxv,-minv)

def copyFrame(inputFrame,outputFrame):
    src = TEMP_FOLDER+"/frame{:06d}".format(inputFrame+1)+".jpg"
    dst = TEMP_FOLDER+"/newFrame{:06d}".format(outputFrame+1)+".jpg"
    if not os.path.isfile(src):
        return False
    copyfile(src, dst)
    if outputFrame%20 == 19:
        print(str(outputFrame+1)+" time-altered frames saved.")
    return True

def inputToOutputFilename(filename):
    dotIndex = filename.rfind(".")
    return filename[:dotIndex]+"_ALTERED"+filename[dotIndex:]

def createPath(s):
    #assert (not os.path.exists(s)), "The filepath "+s+" already exists. Don't want to overwrite it. Aborting."

    try:  
        os.mkdir(s)
    except OSError:  
        #assert False, "Creation of the directory %s failed. (The TEMP folder may already exist. Delete or rename it, and try again.)"
        print("Creation of the directory %s failed. (The TEMP folder may already exist. Delete or rename it, and try again.)")
        
def deletePath(s): # Dangerous! Watch out!
    try:  
        rmtree(s,ignore_errors=False)
    except OSError:  
        print ("Deletion of the directory %s failed" % s)
        print(OSError)

def delete_temp_file(file_name):
    try:  
        os.remove(file_name)
    except OSError:  
        print ("Deletion of file {} failed".format(file_name))
        print(OSError)

parser = argparse.ArgumentParser(description='Modifies a video file to play at different speeds when there is sound vs. silence.')
parser.add_argument('--input_file', type=str,  help='the video file you want modified')
parser.add_argument('--url', type=str, help='A youtube url to download and process')
parser.add_argument('--output_file', type=str, default="", help="the output file. (optional. if not included, it'll just modify the input file name)")
parser.add_argument('--silent_threshold', type=float, default=0.03, help="the volume amount that frames' audio needs to surpass to be consider \"sounded\". It ranges from 0 (silence) to 1 (max volume)")
parser.add_argument('--silent_threshold_abs', type=float, default=540, help="absolute value to edit. Videos are around ~9000*0.06")
parser.add_argument('--sounded_speed', type=float, default=1.00, help="the speed that sounded (spoken) frames should be played at. Typically 1.")
parser.add_argument('--silent_speed', type=float, default=5.00, help="the speed that silent frames should be played at. 999999 for jumpcutting.")
parser.add_argument('--frame_margin', type=float, default=1, help="some silent frames adjacent to sounded frames are included to provide context. How many frames on either the side of speech should be included? That's this variable.")
parser.add_argument('--sample_rate', type=int, default=44100, help="sample rate of the input and output videos")
parser.add_argument('--frame_rate', type=float, default=30, help="frame rate of the input and output videos. optional... I try to find it out myself, but it doesn't always work.")
parser.add_argument('--frame_quality', type=int, default=3, help="quality of frames to be extracted from input video. 1 is highest, 31 is lowest, 3 is the default.")
parser.add_argument('--chunk_duration', type=float, default=10, help="chunk duration in minutes to split the video before processing to reduce disk usage")

args = parser.parse_args()


TEMP_FOLDER = "TEMP" # "/media/jack/CA64-5E88/TEMP"
frame_rate = args.frame_rate
SAMPLE_RATE = args.sample_rate
CHUNK_DUR = args.chunk_duration
SILENT_THRESHOLD = args.silent_threshold
SILENT_THRESHOLD_ABS = args.silent_threshold_abs
FRAME_SPREADAGE = args.frame_margin
NEW_SPEED = [args.silent_speed, args.sounded_speed]
if args.url != None:
    INPUT_FILE = downloadFile(args.url)
else:
    INPUT_FILE = args.input_file
URL = args.url
FRAME_QUALITY = args.frame_quality

assert INPUT_FILE != None , "why u put no input file, that dum"
    
if len(args.output_file) >= 1:
    OUTPUT_FILE = args.output_file
else:
    OUTPUT_FILE = inputToOutputFilename(INPUT_FILE)

# Divide into chunks of size < 500MB
# 1 min of video ===> 4.25 MB
# 100MB of video ===> ~24 min

 
#file_size = os.path.getsize(INPUT_FILE) / (1024*1024) # in megabytes (1024*1024 Bytes)
#num_chunks = (file_size // CHUNK_SIZE) + 1
piece_dur = CHUNK_DUR * 60 # 25 minutes in seconds
command = "ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "+INPUT_FILE
print((subprocess.run(command, capture_output=True, shell=True).stdout))
file_duration = float(subprocess.run(command, capture_output=True, shell=True).stdout)

num_chunks = int((file_duration // piece_dur) + 1)


chunk_names = []
if num_chunks == 1:
    chunk_names.append(INPUT_FILE)
else:
    print("Spliting source video into {} pieces".format(num_chunks))
    # ffmpeg does not split correctly as the beggining of each piece is delayed/don't show video, only audio
    # Thats why I use mkvmerge from mkvtoolnix package
    command = "mkvmerge --split " + str(piece_dur) + "s " + INPUT_FILE + " -o " + INPUT_FILE[:-4]+"-split"+INPUT_FILE[-4:]
    subprocess.call(command, shell=True)

    # mkvmerge automatically adds "-001", "-002", etc, to the "-o" given param between "filename" and ".mkv"
    chunk_names = [INPUT_FILE[:-4] + "-split-{:03}.{}".format(i+1, INPUT_FILE[-3:]) for i in range(num_chunks)]
    print("Splitting done. Chunk names:")
    for file_name in chunk_names:
        print(file_name) 


def jumpcutter(input_file, frame_rate):
    input_file = input_file

    output_file = inputToOutputFilename(input_file)

    if os.path.isfile(output_file):
        print("Output file \"{}\" already exists. Ignoring this part to process.".format(output_file))
        return

    
    AUDIO_FADE_ENVELOPE_SIZE = 400 # smooth out transitiion's audio by quickly fading in/out (arbitrary magic number whatever)
        
    createPath(TEMP_FOLDER)

    command = "ffmpeg -i "+input_file+" -qscale:v "+str(FRAME_QUALITY)+" "+TEMP_FOLDER+"/frame%06d.jpg -hide_banner"
    subprocess.call(command, shell=True)

    noise_reduction = " -af afftdn"
    command = "ffmpeg -i "+input_file+noise_reduction+" -ab 160k -ac 2 -ar "+str(SAMPLE_RATE)+" -vn "+TEMP_FOLDER+"/audio.wav"

    subprocess.call(command, shell=True)

    command = "ffmpeg -i "+TEMP_FOLDER+"/input.mp4 2>&1 -b:v 50000"
    f = open(TEMP_FOLDER+"/params.txt", "w")
    subprocess.call(command, shell=True, stdout=f)



    sampleRate, audioData = wavfile.read(TEMP_FOLDER+"/audio.wav")
    audioSampleCount = audioData.shape[0]
    maxAudioVolume = getMaxVolume(audioData)
    print("maxAudioVolume:", maxAudioVolume)

    f = open(TEMP_FOLDER+"/params.txt", 'r+')
    pre_params = f.read()
    f.close()
    params = pre_params.split('\n')
    for line in params:
        m = re.search('Stream #.*Video.* ([0-9]*) fps',line)
        if m is not None:
            frame_rate = float(m.group(1))

    samplesPerFrame = sampleRate/frame_rate

    audioFrameCount = int(math.ceil(audioSampleCount/samplesPerFrame))

    hasLoudAudio = np.zeros((audioFrameCount))



    for i in range(audioFrameCount):
        start = int(i*samplesPerFrame)
        end = min(int((i+1)*samplesPerFrame),audioSampleCount)
        audiochunks = audioData[start:end]
        maxchunksVolume = float(getMaxVolume(audiochunks))/maxAudioVolume
        print("maxchunksVolume = float(getMaxVolume(audiochunks))/maxAudioVolume",maxchunksVolume,float(getMaxVolume(audiochunks)),maxAudioVolume)
        #maxchunksVolume = float(getMaxVolume(audiochunks))
        #if maxchunksVolume >= SILENT_THRESHOLD_ABS:
        if maxchunksVolume >= SILENT_THRESHOLD:
            hasLoudAudio[i] = 1

    chunks = [[0,0,0]]
    shouldIncludeFrame = np.zeros((audioFrameCount))
    for i in range(audioFrameCount):
        start = int(max(0,i-FRAME_SPREADAGE))
        end = int(min(audioFrameCount,i+1+FRAME_SPREADAGE))
        shouldIncludeFrame[i] = np.max(hasLoudAudio[start:end])
        if (i >= 1 and shouldIncludeFrame[i] != shouldIncludeFrame[i-1]): # Did we flip?
            chunks.append([chunks[-1][1],i,shouldIncludeFrame[i-1]])

    chunks.append([chunks[-1][1],audioFrameCount,shouldIncludeFrame[i-1]])
    chunks = chunks[1:]

    outputAudioData = np.zeros((0,audioData.shape[1]))
    outputPointer = 0

    lastExistingFrame = None
    for chunk in chunks:
        audioChunk = audioData[int(chunk[0]*samplesPerFrame):int(chunk[1]*samplesPerFrame)]
        
        sFile = TEMP_FOLDER+"/tempStart.wav"
        eFile = TEMP_FOLDER+"/tempEnd.wav"
        wavfile.write(sFile,SAMPLE_RATE,audioChunk)
        with WavReader(sFile) as reader:
            with WavWriter(eFile, reader.channels, reader.samplerate) as writer:
                tsm = phasevocoder(reader.channels, speed=NEW_SPEED[int(chunk[2])])
                tsm.run(reader, writer)
        _, alteredAudioData = wavfile.read(eFile)
        leng = alteredAudioData.shape[0]
        endPointer = outputPointer+leng
        outputAudioData = np.concatenate((outputAudioData,alteredAudioData/maxAudioVolume))

        #outputAudioData[outputPointer:endPointer] = alteredAudioData/maxAudioVolume

        # smooth out transitiion's audio by quickly fading in/out
        
        if leng < AUDIO_FADE_ENVELOPE_SIZE:
            outputAudioData[outputPointer:endPointer] = 0 # audio is less than 0.01 sec, let's just remove it.
        else:
            premask = np.arange(AUDIO_FADE_ENVELOPE_SIZE)/AUDIO_FADE_ENVELOPE_SIZE
            mask = np.repeat(premask[:, np.newaxis],2,axis=1) # make the fade-envelope mask stereo
            outputAudioData[outputPointer:outputPointer+AUDIO_FADE_ENVELOPE_SIZE] *= mask
            outputAudioData[endPointer-AUDIO_FADE_ENVELOPE_SIZE:endPointer] *= 1-mask

        startOutputFrame = int(math.ceil(outputPointer/samplesPerFrame))
        endOutputFrame = int(math.ceil(endPointer/samplesPerFrame))
        for outputFrame in range(startOutputFrame, endOutputFrame):
            inputFrame = int(chunk[0]+NEW_SPEED[int(chunk[2])]*(outputFrame-startOutputFrame))
            didItWork = copyFrame(inputFrame,outputFrame)
            if didItWork:
                lastExistingFrame = inputFrame
            else:
                copyFrame(lastExistingFrame,outputFrame)

        outputPointer = endPointer

    wavfile.write(TEMP_FOLDER+"/audioNew.wav",SAMPLE_RATE,outputAudioData)

    '''
    outputFrame = math.ceil(outputPointer/samplesPerFrame)
    for endGap in range(outputFrame,audioFrameCount):
        copyFrame(int(audioSampleCount/samplesPerFrame)-1,endGap)
    '''
    
    command = "ffmpeg -framerate "+str(frame_rate)+" -i "+TEMP_FOLDER+"/newFrame%06d.jpg -i "+TEMP_FOLDER+"/audioNew.wav -strict -2 "+output_file
    subprocess.call(command, shell=True)

    deletePath(TEMP_FOLDER)



# Jumpcutter files
for file_name in chunk_names:
    print("Starting processing video file/s.")
    print("Processing {} from {} pieces".format(file_name, len(chunk_names)))
    jumpcutter(file_name, frame_rate)
    print("Done processing \"{}\"".format(file_name))

    if num_chunks > 1 and file_name != INPUT_FILE:
        print("Removing temp file:",file_name)
        delete_temp_file(file_name)
        print("Removing done.")

# Merge files if necessary (only after splitting into parts)

if num_chunks > 1:
    processed_chunk_names = [inputToOutputFilename(chunk_name) for chunk_name in chunk_names]
    command = "mkvmerge -o {}".format(inputToOutputFilename(INPUT_FILE)) + str(processed_chunk_names).replace("', '", " +").replace("['", " ").replace("']", "")
    print("About to run:", command)
    subprocess.call(command, shell=True)
    print("Last merge done!")
    print("Removing temp files...")
    
    # Remove temp files
    for file_name in processed_chunk_names:
        if file_name != INPUT_FILE:
            delete_temp_file(file_name)
            print("Removing done: {}".format(file_name))

print("All done! :)")