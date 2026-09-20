'''
Remplay
Made by Kawediloru
Downloads YouTube videos from Discord and plays them on a Pygame GUI
Last Modified 20 September 2026
'''

###########
# IMPORTS #
###########

import asyncio, discord, glob, numpy as np, os, pyautogui, pygame, sys, yt_dlp
from discord.ext import commands
from moviepy.editor import VideoFileClip, vfx # moviepy==1.0.3
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
from uuid import uuid4





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
        super().__init__(command_prefix='!', intents=intents)

        self.add_command(req)



    async def on_ready(self):
        '''
        Tell when the bot is running
        '''

        print(f"Bot ready: {self.user}")



# Commands for the bot need global scope. Because fuck you I guess?
@commands.command()
async def req(ctx, url):
    '''
    Request command which lets users send video requests in a target channel
    '''

    if ctx.channel.id in DiscordReader.CHANNELS:
        try:
            vidLen = await asyncio.to_thread(YoutubeDownloader.find_video_length, url)

            if vidLen > YoutubeDownloader.MAX_LENGTH:
                await ctx.send(f"Please keep videos under {YoutubeDownloader.MAX_LENGTH} seconds.", delete_after=5.0)
                await ctx.message.add_reaction("❌")
                return
            
            await asyncio.to_thread(YoutubeDownloader.download_video, url)
            await ctx.message.add_reaction("✅")
        
        except Exception as e:
            print(f"Unable to parse message: {e}")
            await ctx.send("An error occurred!", delete_after=5.0)
            await ctx.message.add_reaction("⚠️")
    
    else:
        await ctx.send("Please use the assigned mediashare channel.", delete_after=5.0)



def run_bot():
    '''
    Function to run the Discord bot in a thread
    '''

    bot = DiscordReader()
    bot.run(DiscordReader.TOKEN)





class YoutubeDownloader:
    '''
    Youtube Downloader functions.
    For checking the length of YT videos
    and downloading them if they're valid
    '''

    # customizable rule
    MAX_LENGTH = 60



    @staticmethod
    def find_video_length(url:str):
        '''
        Get the length of the requested video. Or raise an error if it isn't one
        '''

        try:
            info_dict = yt_dlp.YoutubeDL().extract_info(url, download=False)
            return info_dict.get("duration", 0)
        except Exception as e:
            raise e



    @staticmethod
    def download_video(url:str):
        '''
        Downloads the video
        '''

        try:
            global player

            filename = f"video{uuid4().hex}"
            video = yt_dlp.YoutubeDL({"outtmpl": f"{filename}.%(ext)s"})
            video.download(url)

            player.fileQueue.put(next(glob.iglob(f"{filename}.*")))
        
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

    # only for performance
    CQUEUE_SIZE = 5



    def __init__(self):
        '''
        Start the player up by setting up pygame and queue variables
        '''

        pygame.init()
        self.CLOCK = pygame.time.Clock()
        self.WIDTH, self.HEIGHT = pyautogui.size()

        if VideoPlayer.FULLSCREEN: self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else: self.screen = pygame.display.set_mode((self.WIDTH * VideoPlayer.SCALE, self.HEIGHT * VideoPlayer.SCALE))

        self.fileQueue = Queue()
        self.clipQueue = Queue(maxsize=VideoPlayer.CQUEUE_SIZE)

        self.thrQueueManagement = Thread(target=self.fill_clip_queue, daemon=True)
        self.thrQueueManagement.start()



    def fill_clip_queue(self):
        '''
        Populate the clip queue
        '''

        while True:
            try:
                name = self.fileQueue.get()
                clip = self.filename_to_video_object(name)
                self.clipQueue.put(clip)
            except Exception as e:
                print(f"Failed to append clip: {e}")

    

    def filename_to_video_object(self, name:str):
        '''
        Function that creates a clip object from
        the filename so it can play when loaded.
        '''

        try:
            # Video needs to be rotated 90 degrees and mirrored cuz sure why not.
            clip = VideoFileClip(name, target_resolution=(self.HEIGHT * VideoPlayer.SCALE, None)).rotate(90).fx(vfx.mirror_y).volumex(VideoPlayer.VOLUME/100)
            return clip
        
        except OSError as e:
            raise e



    @staticmethod
    def stop_video(clip):
        '''
        Stop the currently playing clip and signal the next one
        '''

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except pygame.error as e:
            print(f"Failed to unload music: e")
        
        clip.close()



    @staticmethod
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
            try:
                VideoPlayer.play_audio(clip)
            except Exception as e:
                print(f"Current audio failed to load: {e}")
        
        try:
            for frame in clip.iter_frames(dtype="uint8"):
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
                clipRect = frameSurface.get_rect(center=((self.WIDTH * VideoPlayer.SCALE) // 2, (self.HEIGHT * VideoPlayer.SCALE) // 2))
                self.screen.fill((0, 0, 0))
                self.screen.blit(frameSurface, clipRect)
                pygame.display.update()
                
                self.CLOCK.tick(clip.fps)
        
        except OSError as e:
            print(f"Current video failed to load: {e}")
        
        VideoPlayer.stop_video(clip)



    def manage_videos(self):
        '''
        Function to manage the playing of videos in generallll ig
        Basically waits for a video to enter the queue before playing
        '''
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()

            try:
                clip = self.clipQueue.get_nowait()
                self.play_video(clip)
            except:
                pass




########
# MAIN #
########

# Preemptively set path to vids folder to download/find them
os.chdir(f"{Path(__file__).resolve().parent}/vids")

# Create the video player object
player = VideoPlayer()

# Run the discord bot
botThread = Thread(target=run_bot, daemon=True)
botThread.start()

# Run the video management loop
player.manage_videos()
