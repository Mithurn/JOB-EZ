import time
import random
import math

# ============================================================
#  HUMANIZATION LAYER - AVOID DETECTION
# ============================================================

def human_sleep(min_seconds=2, max_seconds=5, variance=0.3):
    """
    Advanced sleep with occasional 'distraction' pauses.
    
    Args:
        min_seconds: Minimum sleep time
        max_seconds: Maximum sleep time
        variance: Probability (0-1) of adding extra distraction delay
    """
    base_sleep = random.uniform(min_seconds, max_seconds)
    
    # 30% chance of "getting distracted" (extra 2-8 sec pause)
    if random.random() < variance:
        distraction = random.uniform(2, 8)
        base_sleep += distraction
    
    time.sleep(base_sleep)


def human_type(page, selector, text, delay_min=50, delay_max=150, 
               mistake_probability=0.05, pause_probability=0.15):
    """
    Types with realistic human behavior:
    - Random typing speed variations
    - Occasional typos + backspace corrections
    - Random pauses (like thinking)
    
    Args:
        mistake_probability: Chance to make a typo per character (5% default)
        pause_probability: Chance to pause mid-typing (15% default)
    """
    try:
        element = page.locator(selector)
        element.click()  # Focus the field first
        human_sleep(0.1, 0.3)
        
        for i, char in enumerate(text):
            # Occasionally make a typo
            if random.random() < mistake_probability:
                wrong_char = random.choice('qwertyuiopasdfghjklzxcvbnm')
                element.press(wrong_char)
                time.sleep(random.uniform(0.1, 0.3))
                element.press('Backspace')
                time.sleep(random.uniform(0.05, 0.15))
            
            # Type the correct character
            element.press(char)
            
            # Variable typing speed (humans slow down on complex chars)
            if char in '!@#$%^&*()_+-={}[]|\\:";\'<>?,./':
                delay = random.uniform(delay_max, delay_max * 1.5)
            else:
                delay = random.uniform(delay_min, delay_max)
            
            time.sleep(delay / 1000)  # Convert ms to seconds
            
            # Random pauses (like thinking or reading)
            if random.random() < pause_probability:
                time.sleep(random.uniform(0.3, 1.2))
        
    except Exception as e:
        print(f"⚠️ Could not type in {selector}: {e}")


def human_scroll(page, read_time=True):
    """
    Scrolls like a human reading content:
    - Variable scroll speeds
    - Occasional scroll-ups (re-reading)
    - Pauses to "read" sections
    """
    try:
        # Get page height
        page_height = page.evaluate("document.body.scrollHeight")
        viewport_height = page.evaluate("window.innerHeight")
        
        current_position = 0
        
        # Scroll in chunks (like reading sections)
        while current_position < page_height - viewport_height:
            # Random scroll distance (200-800px)
            scroll_distance = random.randint(200, 800)
            
            # Smooth scroll with easing (not instant)
            steps = random.randint(10, 20)
            for step in range(steps):
                micro_scroll = scroll_distance / steps
                page.mouse.wheel(0, micro_scroll)
                time.sleep(0.02)  # 20ms between micro-scrolls
            
            current_position += scroll_distance
            
            # Pause to "read" (if enabled)
            if read_time:
                time.sleep(random.uniform(1, 3))
            
            # 20% chance to scroll back up slightly (re-reading)
            if random.random() < 0.2:
                page.mouse.wheel(0, -random.randint(50, 200))
                time.sleep(random.uniform(0.5, 1.5))
        
        # Final pause at bottom
        human_sleep(1, 2)
        
    except Exception as e:
        print(f"⚠️ Scrolling failed: {e}")


def human_mouse_move(page, x, y, duration=0.5):
    """
    Moves mouse in a curved path (Bezier-like) instead of straight line.
    Mimics natural hand movement.
    """
    try:
        # Get current mouse position
        current_x = page.evaluate("window.mouseX || window.innerWidth / 2")
        current_y = page.evaluate("window.mouseY || window.innerHeight / 2")
        
        # Generate curve control points
        control_x1 = current_x + random.uniform(-100, 100)
        control_y1 = current_y + random.uniform(-100, 100)
        control_x2 = x + random.uniform(-50, 50)
        control_y2 = y + random.uniform(-50, 50)
        
        # Move in steps along the curve
        steps = random.randint(15, 30)
        for i in range(steps + 1):
            t = i / steps
            # Cubic Bezier formula
            bx = (1-t)**3 * current_x + 3*(1-t)**2*t * control_x1 + \
                 3*(1-t)*t**2 * control_x2 + t**3 * x
            by = (1-t)**3 * current_y + 3*(1-t)**2*t * control_y1 + \
                 3*(1-t)*t**2 * control_y2 + t**3 * y
            
            page.mouse.move(bx, by)
            time.sleep(duration / steps)
        
        # Store final position
        page.evaluate(f"window.mouseX = {x}; window.mouseY = {y}")
        
    except Exception as e:
        print(f"⚠️ Mouse move failed: {e}")


def human_click(page, selector, move_mouse=True):
    """
    Clicks with human-like behavior:
    - Moves mouse to element first
    - Slight position randomness (doesn't click center pixel)
    - Brief hover before click
    """
    try:
        element = page.locator(selector)
        box = element.bounding_box()
        
        if box and move_mouse:
            # Click random point within element (not always center)
            click_x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
            click_y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
            
            human_mouse_move(page, click_x, click_y, duration=random.uniform(0.3, 0.7))
            time.sleep(random.uniform(0.1, 0.3))  # Brief hover
        
        element.click()
        human_sleep(0.5, 1.5)
        
    except Exception as e:
        print(f"⚠️ Could not click {selector}: {e}")


def random_micro_movements(page, duration=10):
    """
    Simulates idle mouse movements (like a user reading).
    Call this occasionally when the bot is "waiting" for pages to load.
    """
    try:
        end_time = time.time() + duration
        while time.time() < end_time:
            # Small random movements
            dx = random.randint(-50, 50)
            dy = random.randint(-30, 30)
            page.mouse.move(dx, dy, steps=random.randint(3, 8))
            time.sleep(random.uniform(0.5, 2))
    except:
        pass


def simulate_reading_pattern(page, selector):
    """
    Simulates reading text by moving mouse over it.
    Use this for job descriptions before clicking "Apply".
    """
    try:
        element = page.locator(selector)
        box = element.bounding_box()
        
        if box:
            # Start at top-left of text
            x = box['x'] + 20
            y = box['y'] + 10
            
            # Move across several "lines" of text
            for line in range(random.randint(3, 6)):
                # Move right (reading)
                end_x = x + random.uniform(200, 400)
                human_mouse_move(page, end_x, y, duration=random.uniform(0.8, 1.5))
                
                # Move down to next line
                y += random.uniform(20, 35)
                time.sleep(random.uniform(0.3, 0.8))
    except:
        pass