from django.db import models

class SeedImage(models.Model):
    image = models.ImageField(upload_to='seed_images/')
    annotated_image = models.ImageField(upload_to='seed_images/annotated/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SeedImage {self.id} - {self.image.name}"

class SeedMeasurement(models.Model):
    seed_image = models.ForeignKey(SeedImage, on_delete=models.CASCADE, related_name='measurements')
    seed_number = models.PositiveIntegerField()
    width_mm = models.FloatField()
    height_mm = models.FloatField()

    def __str__(self):
        return f"Seed {self.seed_number} - W:{self.width_mm}mm H:{self.height_mm}mm"