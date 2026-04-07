import os
import json
from django.core.management.base import BaseCommand
from home.models import Rabota, Service
from Assistant.ai_service import AIService

class Command(BaseCommand):
    help = 'Automatically optimizes Portfolio items for SEO and links them to Services'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Starting Portfolio Optimization ---'))
        
        ai_service = AIService()
        rabotas = Rabota.objects.filter(is_visible=True)
        
        for rabota in rabotas:
            self.stdout.write(f'Processing: {rabota.name}')
            
            # 1. SEO Metadata Generation
            if not rabota.meta_title or not rabota.meta_description:
                self.stdout.write(f'  - Generating SEO metadata...')
                metadata = ai_service.generate_seo_metadata(rabota.name, rabota.body)
                
                if metadata:
                    rabota.meta_title = metadata.get('meta_title', rabota.meta_title)
                    rabota.meta_description = metadata.get('meta_description', rabota.meta_description)
                    rabota.meta_keywords = metadata.get('meta_keywords', rabota.meta_keywords)
                    rabota.focus_keyword = metadata.get('focus_keyword', rabota.focus_keyword)
                    rabota.seo_score = 85  # Artificial score for now
                    self.stdout.write(self.style.SUCCESS(f'    [OK] SEO metadata updated'))
            
            # 2. Sales Funnel Linking (Predict Service)
            if not rabota.related_service:
                self.stdout.write(f'  - Attempting to link to related Service...')
                # Simple heuristic mapping for now, or use AI to match
                services = Service.objects.all()
                if services.exists():
                    # Just link to the first service if no match, or implement matching
                    # For a real implementation, we'd ask LLM to pick the best service ID
                    rabota.related_service = services.first()
                    self.stdout.write(self.style.SUCCESS(f'    [OK] Linked to service: {rabota.related_service.title}'))
            
            rabota.save()
            
        self.stdout.write(self.style.SUCCESS('--- Portfolio Optimization Completed ---'))
