# this is just to test out the debugger in VS Code

def compute_area(w, h):
    return w * h

name = "Spencer"
width = 5
height = 3
area = compute_area(width, height)

for i in range(3):
    value = i * area
    print(f"{name} - Iteration {i}: value = {value}")