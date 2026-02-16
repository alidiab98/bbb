import os
import time
import cv2
import numpy as np
from playwright.sync_api import sync_playwright

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

class GUI:
    def __init__(self, page):
        self.page = page

    def screenshot(self, path="screenshot.png"):
        try:
            self.page.screenshot(path=path)
            return path
        except Exception as e:
            log(f"Screenshot failed: {e}")
            return None

    def search(self, template_path, threshold=0.8):
        """
        Searches for the template image on the current screen.
        Returns coordinates (x, y) if found, else None.
        Appends .png if missing.
        """
        # Ensure extension
        if not template_path.endswith('.png'):
            template_path += ".png"
        
        # Check if file exists
        if not os.path.exists(template_path):
            # log(f"Template not found: {template_path}")
            return None

        # Take screenshot for analysis
        screen_path = "current_screen.png"
        self.screenshot(screen_path)

        # Read images
        img_rgb = cv2.imread(screen_path)
        template = cv2.imread(template_path)
        
        if img_rgb is None or template is None:
            return None

        # Matching
        try:
            res = cv2.matchTemplate(img_rgb, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold:
                # Calculate center
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return {"x": center_x, "y": center_y}
        except Exception as e:
            log(f"CV Error: {e}")
        
        return None

    def click(self, target, realistic=False):
        if target:
            # Playwright mouse click
            self.page.mouse.click(target['x'], target['y'])
            # log(f"Clicked at {target['x']}, {target['y']}")

    def clickAndWrite(self, target, text):
        if target:
            self.click(target)
            time.sleep(0.5)
            self.page.keyboard.type(text)

    def refresh(self):
        try:
            self.page.reload()
        except:
            pass

class BigBlueButtonBot:
    def __init__(self, bot_name, url):
        self.bot_name = bot_name
        self.url = url
        self.driver = None  # Playwright Page object
        self.log_browser = None # Opsional handling

    def joinMeeting(self):
        result = "fail"
        state = "init"
        try_to_close_modal = 0
        
        stop_signal_path = "/usr/local/bin/recordings/stop_signal.txt"
        time_start = time.time()

        with sync_playwright() as p:
            current_dir = os.getcwd() # Ensure we search images relative to CWD
            
            # Launch Browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080}, # Standard resolution for image matching
                record_video_dir="recordings/"
            )
            # Permission workaround for audio/cam (if needed, though we are bots)
            context.grant_permissions(['microphone', 'camera'])
            
            page = context.new_page()
            self.driver = page
            # Initialize GUI helper with the current page
            gui = GUI(page)

            log(f"Navigating to {self.url}")
            try:
                page.goto(self.url, timeout=60000)
            except Exception as e:
                log(f"Navigation error: {e}")
                return "navigation_fail"

            # Log console
            page.on("console", lambda msg: print(f"BROWSER: {msg.text}"))

            while True:
                # Screenshot handled inside gui.search usually, but loop requires one for "logging" or general update
                # The original code did gui.screenshot() at start of loop.
                gui.screenshot("loop_screenshot.png")
                time.sleep(1)

                # Check stop signal
                if os.path.exists(stop_signal_path):
                    log("stop_signal")
                    result = "stop signal"
                    break

                # Time limit
                if time.time() - time_start >= 1200:
                    log("time_limit")
                    result = "join time limit"
                    break

                log(f"state {state}")

                # External browser logging hook if exists
                if self.log_browser:
                    try:
                        self.log_browser()
                    except:
                        pass
                
                # --- STATE MACHINE (Image Based) ---
                
                if state == "init":
                    target = gui.search('bigbluebutton/name_input')
                    
                    if target is not None:
                        gui.clickAndWrite(target, self.bot_name)
                        state = 'bot name writen'
                        continue
                
                if state == 'bot name writen':
                    target = gui.search('bigbluebutton/join_meeting')
                    if target is not None:
                        gui.click(target=target, realistic=False)
                        state = 'Join button clicked'
                        # Wait for load
                        page.wait_for_timeout(2000)
                        continue
                    
                if state == 'Join button clicked':
                    # Check Listen Only
                    listen_only = gui.search('bigbluebutton/listen_onley')
                    if listen_only is not None:
                        gui.click(listen_only)
                        state = 'audio_configured'
                        continue

                    # Check Join Audio (Alternative)
                    target = gui.search('bigbluebutton/join_audio')
                    if target is not None:
                        gui.click(target)
                        state = 'audio_configured'
                        continue
                
                if state == 'audio_configured':
                    # Check if audio modal is still up or re-appeared
                    target = gui.search('bigbluebutton/join_audio')
                    if target is not None:
                        gui.click(target)
                        continue
                    
                    # Try closing modal
                    target = gui.search('bigbluebutton/modal_exit')
                    if target is not None:
                        gui.click(target)
                        try_to_close_modal += 1
                    else:
                        try_to_close_modal += 1

                    if try_to_close_modal >= 5:
                        # Logic to refresh if stuck
                        if self.driver:
                            try:
                                self.driver.evaluate("window.onbeforeunload = null;")
                            except:
                                pass
                        
                        gui.refresh()
                        time.sleep(5)
                        
                        target = gui.search('bigbluebutton/cancel')
                        if target is not None:
                            gui.click(target)
                            time.sleep(1)

                        result = "success"
                        break    

            browser.close()
            
        return result

# Usage Example
if __name__ == "__main__":
    # Ensure bigbluebutton folder exists with images for this to work
    bot = BigBlueButtonBot("BotUser", "https://demo.bigbluebutton.org/rooms/h4p-fby-2fk-yba/join")
    print(bot.joinMeeting())
