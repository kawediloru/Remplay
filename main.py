'''
Remplay
Made by Kawediloru
Downloads YouTube videos from Discord and plays them on a Pygame GUI
Last Modified 20 September 2026
'''

###########
# IMPORTS #
###########

import discord, glob, numpy as np, os, pyautogui, pygame, sys, yt_dlp
from discord.ext import commands
from moviepy.editor import VideoFileClip, vfx # moviepy==1.0.3
from pathlib import Path
from random import choice
from threading import Thread
from time import sleep





###########
# CLASSES #
###########

class DiscordReader(commands.Bot):
    '''
    Discord Reader bot.
    Uses the TOKEN and Reads from the channel(s) in CHANNELS
    Functions as the input for the mediashare
    '''

    # Bot token and channels to read from
    TOKEN = "" # Bot token goes here
    CHANNELS = {} # Channels to read from go here

    def __init__(self):
        '''
        Set up intents and commands
        '''

        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        super().__init__(command_prefix='!', intents=intents)

        self.add_command(req)



    async def on_ready(self):
        '''
        Tell when the bot is running
        '''

        print(f"Bot ready: {self.user}")



# Commands for the bot need global scope. Because fuck you I guess?
@commands.command()
async def req(ctx, *, msg):
    '''
    Request command which lets users send video requests in a target channel
    '''

    if ctx.channel.name in DiscordReader.CHANNELS:
        try:
            vidURL = msg.split(' ')[0]
            vidLen = YoutubeDownloader.find_video_length(vidURL)

            if (vidLen <= YoutubeDownloader.MAX_LENGTH):
                YoutubeDownloader.download_video(vidURL)
                await ctx.message.add_reaction("✅")
            else:
                await ctx.send(f"Please keep videos under {YoutubeDownloader.MAX_LENGTH} seconds.", delete_after=5.0)
                await ctx.message.add_reaction("❌")
        
        except:
            pass
    
    else:
        await ctx.send("Please use the assigned mediashare channel.", delete_after=5.0)




videoIndex = 0
class YoutubeDownloader:
    '''
    Youtube Downloader functions.
    For checking the length of YT videos
    and downloading them if they're valid
    '''

    # Settings
    MAX_LENGTH = 60



    def find_video_length(url:str):
        '''
        Get the length of the requested video. Or raise an error if it isn't one
        '''

        try:
            info_dict = yt_dlp.YoutubeDL().extract_info(url, download=False)
            return info_dict.get("duration", 0)
        except Exception as e:
            raise e



    def download_video(url:str):
        '''
        Downloads the video
        '''

        try:
            global videoIndex
            global player

            video = yt_dlp.YoutubeDL({"outtmpl": f"video{videoIndex}.%(ext)s"})
            video.download(url)

            player.fileQueue.append(next(glob.iglob(f"video{videoIndex}.*")))

            videoIndex += 1
        
        except Exception as e:
            raise e





class VideoPlayer:
    '''
    Video player functions.
    Uses a queue to play videos in order within its
    own window, which can then be displayed in OBS
    '''

    # customization
    FULLSCREEN = True
    SCALE = 1
    VOLUME = 100

    # i suggest not touching these
    WIDTH, HEIGHT = pyautogui.size()
    CQUEUE_SIZE = 5
    SLEEP_LEN = 1



    def __init__(self):
        '''
        Start the player up by setting up pygame and queue variables
        '''

        pygame.init()
        self.CLOCK = pygame.time.Clock()
        if VideoPlayer.FULLSCREEN: self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else: self.screen = pygame.display.set_mode((VideoPlayer.WIDTH * VideoPlayer.SCALE, VideoPlayer.HEIGHT * VideoPlayer.SCALE))

        self.fileQueue = []
        self.clipQueue = []

        self.thrQueueManagement = Thread(target=self.fill_clip_queue, daemon=True)
        self.thrQueueManagement.start()

        self.thrVidManagement = Thread(target=self.manage_videos, daemon=True)
        self.thrVidManagement.start()



    def fill_clip_queue(self):
        '''
        Check if the queues can be populated
        '''

        while True:
            if len(self.clipQueue) < VideoPlayer.CQUEUE_SIZE:
                try:
                    name = self.fileQueue.pop(0)
                    clip = self.filename_to_video_object(name)
                    self.clipQueue.append(clip)
                except:
                    pass
            
            sleep(VideoPlayer.SLEEP_LEN)

    

    def filename_to_video_object(self, name:str):
        '''
        Function that creates a clip object from
        the filename so it can play when loaded.
        '''

        try:
            clip = VideoFileClip(name, target_resolution=(VideoPlayer.HEIGHT * VideoPlayer.SCALE, None)).rotate(90).fx(vfx.mirror_y).volumex(VideoPlayer.VOLUME/100)
            return clip
        
        except OSError as e:
            print(f"{e}; Bad File in List Skipped")
            return None


    
    def stop_video(clip):
        '''
        Stop the currently playing clip and signal the next one
        '''

        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        clip.close()



    def play_audio(clip):
        '''
        Function to play the audio of a clip when called (through play_video)
        Creates a temporary audio file to play the sound from cuz it's easy that way
        '''

        clip.audio.write_audiofile("cur.wav", fps=44100, verbose=False, logger=None)
        pygame.mixer.music.load("cur.wav")
        pygame.mixer.music.play()



    def play_video(self, clip):
        '''
        Function that actively plays a video to the screen.
        '''
        
        # if there's audio, play it
        if clip.audio:
            try: VideoPlayer.play_audio(clip)
            except Exception as e: print(f"Current audio failed to load: {e}")
        
        try:
            for frame in clip.iter_frames(fps=clip.fps, dtype="uint8"):
                # check for events (also to tick pygame)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        VideoPlayer.stop_video(clip)
                        sys.exit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            VideoPlayer.stop_video(clip)
                            return
                
                # draw it properly
                frameSurface = pygame.surfarray.make_surface(frame)
                clipRect = frameSurface.get_rect(center=((VideoPlayer.WIDTH * VideoPlayer.SCALE) // 2, (VideoPlayer.HEIGHT * VideoPlayer.SCALE) // 2))
                self.screen.fill((0, 0, 0))
                self.screen.blit(frameSurface, clipRect)
                pygame.display.update()
                
                self.CLOCK.tick(clip.fps)
        
        except OSError as e: print(f"Current video failed to load: {e}")
        
        VideoPlayer.stop_video(clip)



    def manage_videos(self):
        '''
        Function to manage the playing of videos in generallll ig
        Basically waits for a video to enter the queue before playing
        '''
        while True:
            while (len(self.clipQueue) == 0):
                sleep(VideoPlayer.SLEEP_LEN)
            
            self.play_video(self.clipQueue.pop(0))





########
# MAIN #
########

# Preemptively set path to vids folder to download/find them
os.chdir(f"{Path(__file__).resolve().parent}/vids")

# Create the video player object
player = VideoPlayer()

# Run the discord bot
bot = DiscordReader()
bot.run(DiscordReader.TOKEN)
