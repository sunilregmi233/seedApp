import os
import cv2
import numpy as np
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from imutils import perspective
from scipy.spatial.distance import euclidean
import pandas as pd
from django.core.files.base import ContentFile
from .models import SeedImage, SeedMeasurement
import tempfile


# Folder to save uploaded images
MEDIA_ROOT = 'media/'

# Store measurements globally (simplified; for production use DB)
MEASUREMENTS = []

def index(request):
    # Pass flag if measurements exist
    context = {
        'measurements_exist': len(MEASUREMENTS) > 0
    }
    return render(request, 'measure/index.html', context)

def process_image(request):
    if request.method == 'POST' and request.FILES.get('image'):

        image_file = request.FILES['image']

        # Create SeedImage instance and save uploaded image
        seed_image = SeedImage.objects.create(image=image_file)

        # Full path to saved image
        image_path = seed_image.image.path

        # Get reference points from POST
        try:
            x1 = int(request.POST['x1'])
            y1 = int(request.POST['y1'])
            x2 = int(request.POST['x2'])
            y2 = int(request.POST['y2'])
        except Exception:
            seed_image.delete()
            return HttpResponse("Invalid reference points", status=400)

        # Load image via cv2
        image = cv2.imread(image_path)
        if image is None:
            seed_image.delete()
            return HttpResponse("Failed to read image", status=400)

        # Calibration
        REF_LENGTH_MM = 10.0  # 1 cm reference box width in mm
        w_ref = abs(x2 - x1)
        pixels_per_mm = w_ref / REF_LENGTH_MM

        # Preprocess for contour detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (9, 9), 0)
        edged = cv2.Canny(blur, 50, 100)
        edged = cv2.dilate(edged, None, iterations=1)
        edged = cv2.erode(edged, None, iterations=1)

        cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        MIN_CONTOUR_AREA = 100
        cnts = [c for c in cnts if cv2.contourArea(c) > MIN_CONTOUR_AREA]

        measurements = []
        count = 0
        for cnt in cnts:
            if count >= 10:  # limit to 10 seeds
                break

            box = cv2.minAreaRect(cnt)
            box_points = cv2.boxPoints(box)
            box_points = np.array(box_points, dtype="int")
            box_points = perspective.order_points(box_points)
            (tl, tr, br, bl) = box_points

            # Measure sides in mm
            side1 = euclidean(tl, tr) / pixels_per_mm
            side2 = euclidean(tr, br) / pixels_per_mm

            # Assign height as longer side, width as shorter side
            height_mm, width_mm = sorted([side1, side2], reverse=True)

            # Only include seeds with height between 1 and 7 mm
            if 1 <= height_mm <= 7:
                measurements.append({
                    'seed_number': count + 1,
                    'height_mm': round(height_mm, 2),
                    'width_mm': round(width_mm, 2),
                })

                # Save each measurement to DB
                SeedMeasurement.objects.create(
                    seed_image=seed_image,
                    seed_number=count + 1,
                    height_mm=round(height_mm, 2),
                    width_mm=round(width_mm, 2),
                )

                count += 1

                # Draw annotated box and text on image
                cv2.drawContours(image, [box_points.astype("int")], -1, (0, 255, 0), 2)
                cv2.putText(image, f"{height_mm:.1f}x{width_mm:.1f} mm",
                            (int(tl[0]), int(tl[1]) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

        # Save annotated image to temporary file
        _, temp_filename = tempfile.mkstemp(suffix='.jpg')
        cv2.imwrite(temp_filename, image)

        # Read annotated image content and save to model field
        with open(temp_filename, 'rb') as f:
            seed_image.annotated_image.save(f"annotated_{os.path.basename(seed_image.image.name)}", ContentFile(f.read()))

        os.remove(temp_filename)

        # Redirect to results page for this image
        return redirect('show_results', image_id=seed_image.id)

    return redirect('index')



from django.shortcuts import get_object_or_404

def show_results(request, image_id):
    seed_image = get_object_or_404(SeedImage, id=image_id)
    measurements = seed_image.measurements.all()
    return render(request, 'measure/results.html', {
        'seed_image': seed_image,
        'measurements': measurements,
    })

def export_csv(request, image_id):
    seed_image = get_object_or_404(SeedImage, id=image_id)
    measurements = seed_image.measurements.all()

    if not measurements:
        return HttpResponse("No data to export", status=400)

    data = []
    for m in measurements:
        data.append({
            'Seed #': m.seed_number,
            'Width (mm)': m.width_mm,
            'Height (mm)': m.height_mm,
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="seed_measurements_{image_id}.csv"'
    df.to_csv(path_or_buf=response, index=False)
    return response