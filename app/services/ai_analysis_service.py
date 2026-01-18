"""
AI Analysis Service for monitoring content analysis.

Provides AI-powered analysis of social media content (text and images)
to detect objectives specified in monitoring tasks.

Supports:
- OpenAI GPT-4 Vision
- DeepSeek VL (Vision-Language)

Used for:
- Detecting activities incompatible with sick leave
- Identifying violent behavior or accidents
- Flagging content relevant to investigation objectives
"""
import base64
import httpx
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """
    Service for AI-powered image and content analysis.

    Supports OpenAI and DeepSeek providers for vision-enabled
    analysis of monitoring results.
    """

    # OpenAI configuration
    OPENAI_BASE_URL = "https://api.openai.com/v1"
    OPENAI_CHAT_ENDPOINT = "/chat/completions"
    OPENAI_MODEL = "gpt-4o"  # GPT-4 with vision

    # DeepSeek configuration
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    DEEPSEEK_CHAT_ENDPOINT = "/chat/completions"
    DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek text model (no vision support)

    # Analysis configuration
    MAX_IMAGES_PER_REQUEST = 4
    DEFAULT_MAX_TOKENS = 1000
    TIMEOUT_SECONDS = 60

    # Retry configuration for rate limiting (429 errors)
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 5  # seconds
    MAX_RETRY_DELAY = 60  # seconds

    # Provider capabilities
    VISION_CAPABLE_PROVIDERS = ['openai']  # Providers that support image analysis

    def __init__(self, provider: str = 'deepseek', api_key_model=None):
        """
        Initialize the AI analysis service.

        Args:
            provider: AI provider ('openai' or 'deepseek')
            api_key_model: Optional ApiKey model instance. If not provided,
                          will be loaded from database.
        """
        self.provider = provider.lower()
        self.api_key_model = api_key_model
        self.api_key = None

        if api_key_model:
            self.api_key = api_key_model.get_api_key()
        else:
            self._load_api_key()

    def _load_api_key(self):
        """Load API key from database."""
        from app.models.api_key import ApiKey

        self.api_key_model = ApiKey.get_active_key(self.provider)
        if not self.api_key_model:
            raise ValueError(f"No hay API Key activa para {self.provider}")
        self.api_key = self.api_key_model.get_api_key()

    def _increment_usage(self):
        """Increment API key usage counter."""
        if self.api_key_model:
            try:
                self.api_key_model.increment_usage()
            except Exception as e:
                logger.warning(f"Error incrementing API key usage: {e}")

    def analyze_content(
        self,
        text: Optional[str],
        images: Optional[List[str]],
        objective: str,
        context: Optional[Dict] = None,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze content against monitoring objective.

        Args:
            text: Text content to analyze (can be None)
            images: List of image URLs or base64-encoded images (can be None)
            objective: The monitoring objective/question to detect
            context: Additional context (case info, subject info)
            custom_prompt: Optional custom prompt template

        Returns:
            dict with:
                - success: bool
                - relevance_score: 0-1 float (how relevant to objective)
                - summary: Human-readable summary
                - flags: List of specific concerns detected
                - is_alert: Whether this should be flagged as an alert
                - raw_response: Full AI response
                - provider: Provider used
                - model: Model used
                - error: Error message if failed
        """
        try:
            # Check if images are available
            has_images = bool(images and len(images) > 0)

            # Build the analysis prompt (adapts based on vision capability)
            prompt = self._build_analysis_prompt(text, objective, context, custom_prompt, has_images)

            # Prepare images for API (only for vision-capable providers)
            image_content = []
            if has_images and self.supports_vision():
                image_content = self._prepare_images(images)

            # Call the appropriate provider
            if self.provider == 'openai':
                response = self._call_openai(prompt, image_content)
            elif self.provider == 'deepseek':
                response = self._call_deepseek(prompt, image_content)
            else:
                return {
                    'success': False,
                    'error': f'Proveedor de IA no soportado: {self.provider}'
                }

            # Increment usage
            self._increment_usage()

            # Parse the response
            return self._parse_analysis_response(response)

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'provider': self.provider
            }

    def _build_analysis_prompt(
        self,
        text: Optional[str],
        objective: str,
        context: Optional[Dict],
        custom_prompt: Optional[str],
        has_images: bool = False
    ) -> str:
        """Build the prompt for AI analysis."""
        # Check if this provider can analyze images
        can_analyze_images = self.supports_vision() and has_images

        if custom_prompt:
            # Use custom template with variable substitution
            prompt = custom_prompt
            prompt = prompt.replace('{objective}', objective)
            prompt = prompt.replace('{text}', text or '[Sin texto]')
            if context:
                for key, value in context.items():
                    prompt = prompt.replace(f'{{{key}}}', str(value))
            return prompt

        # Default prompt template
        prompt = f"""Eres un analista de investigación privada en España. Tu tarea es analizar contenido de redes sociales para detectar si cumple con un objetivo de monitorización específico.

## OBJETIVO DE MONITORIZACIÓN:
{objective}

## CONTENIDO A ANALIZAR:
"""
        if text:
            prompt += f"""
### Texto del post:
{text}
"""

        if can_analyze_images:
            prompt += """
### Imágenes adjuntas:
Se adjuntan imágenes del post para tu análisis visual.

## INSTRUCCIONES:
1. Analiza todo el contenido (texto e imágenes) en relación al objetivo.
2. Determina si el contenido es relevante para la investigación.
3. Identifica cualquier elemento que pueda ser significativo.
4. Sé objetivo y preciso en tu análisis.
"""
        else:
            prompt += """
### Nota:
Solo se analiza el texto del post. Las imágenes no están disponibles para análisis.

## INSTRUCCIONES:
1. Analiza el texto en relación al objetivo de monitorización.
2. Determina si el contenido textual es relevante para la investigación.
3. Identifica cualquier elemento que pueda ser significativo.
4. Sé objetivo y preciso en tu análisis.
"""

        prompt += """
## FORMATO DE RESPUESTA:
Responde EXACTAMENTE en el siguiente formato JSON:

```json
{
    "relevance_score": <número entre 0.0 y 1.0>,
    "is_alert": <true si el contenido es altamente relevante al objetivo, false en caso contrario>,
    "summary": "<resumen conciso del análisis en español>",
    "flags": ["<lista de elementos específicos detectados relevantes al objetivo>"],
    "details": {
        "text_analysis": "<análisis del texto>",
        "image_analysis": "<análisis de las imágenes o 'No disponible' si no hay imágenes>",
        "objective_match": "<explicación de cómo el contenido se relaciona con el objetivo>"
    }
}
```

### Criterios de puntuación:
- 0.0-0.2: No relevante
- 0.2-0.4: Posiblemente relacionado pero sin evidencia clara
- 0.4-0.6: Moderadamente relevante, requiere revisión
- 0.6-0.8: Relevante, probable coincidencia con objetivo
- 0.8-1.0: Altamente relevante, clara coincidencia con objetivo

### Criterio para is_alert:
- true: Si relevance_score >= 0.6 O si se detecta algo que claramente contradice o confirma el objetivo
- false: En caso contrario
"""

        if context:
            prompt += f"""

## CONTEXTO ADICIONAL:
- Caso: {context.get('case_name', 'No especificado')}
- Sujeto de investigación: {context.get('subject', 'No especificado')}
- Notas: {context.get('notes', 'Ninguna')}
"""

        return prompt

    def _prepare_images(self, images: List[str]) -> List[Dict]:
        """
        Prepare images for API request.

        Args:
            images: List of image URLs or base64-encoded images

        Returns:
            List of image content dicts for API
        """
        prepared = []
        for i, img in enumerate(images[:self.MAX_IMAGES_PER_REQUEST]):
            if img.startswith('data:image'):
                # Already base64 encoded with data URI
                prepared.append({
                    'type': 'image_url',
                    'image_url': {'url': img}
                })
            elif img.startswith('http://') or img.startswith('https://'):
                # URL - use directly
                prepared.append({
                    'type': 'image_url',
                    'image_url': {'url': img}
                })
            else:
                # Assume it's a base64 string without prefix
                prepared.append({
                    'type': 'image_url',
                    'image_url': {'url': f'data:image/jpeg;base64,{img}'}
                })
        return prepared

    def _call_openai(self, prompt: str, images: List[Dict]) -> Dict:
        """
        Call OpenAI API with vision capabilities.

        Includes retry logic with exponential backoff for rate limiting (429) errors.

        Args:
            prompt: Analysis prompt
            images: List of prepared image dicts

        Returns:
            API response dict
        """
        url = f"{self.OPENAI_BASE_URL}{self.OPENAI_CHAT_ENDPOINT}"

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        # Build message content
        content = [{'type': 'text', 'text': prompt}]
        content.extend(images)

        payload = {
            'model': self.OPENAI_MODEL,
            'messages': [
                {
                    'role': 'user',
                    'content': content
                }
            ],
            'max_tokens': self.DEFAULT_MAX_TOKENS,
            'temperature': 0.3  # Lower temperature for more consistent analysis
        }

        return self._make_request_with_retry(url, headers, payload, 'OpenAI')

    def _call_deepseek(self, prompt: str, images: List[Dict]) -> Dict:
        """
        Call DeepSeek API for text analysis.

        Note: DeepSeek chat model does not support vision/images.
        Images are ignored and only text is analyzed.

        Includes retry logic with exponential backoff for rate limiting (429) errors.

        Args:
            prompt: Analysis prompt
            images: List of prepared image dicts (ignored for DeepSeek)

        Returns:
            API response dict
        """
        url = f"{self.DEEPSEEK_BASE_URL}{self.DEEPSEEK_CHAT_ENDPOINT}"

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        # DeepSeek chat model only supports text - images are not supported
        # Log warning if images were provided
        if images:
            logger.info(f"DeepSeek: Ignoring {len(images)} images (model does not support vision)")

        # Send text-only content (DeepSeek uses simple string content, not array)
        payload = {
            'model': self.DEEPSEEK_MODEL,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': self.DEFAULT_MAX_TOKENS,
            'temperature': 0.3
        }

        return self._make_request_with_retry(url, headers, payload, 'DeepSeek')

    def _make_request_with_retry(
        self,
        url: str,
        headers: Dict,
        payload: Dict,
        provider_name: str
    ) -> Dict:
        """
        Make HTTP request with retry logic for rate limiting.

        Implements exponential backoff for 429 (Too Many Requests) errors.

        Args:
            url: API endpoint URL
            headers: Request headers
            payload: Request body
            provider_name: Provider name for logging

        Returns:
            API response dict

        Raises:
            httpx.HTTPStatusError: If request fails after all retries
        """
        last_exception = None
        delay = self.INITIAL_RETRY_DELAY

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=self.TIMEOUT_SECONDS) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    return response.json()

            except httpx.HTTPStatusError as e:
                last_exception = e

                # Only retry on 429 (rate limit) errors
                if e.response.status_code == 429:
                    if attempt < self.MAX_RETRIES:
                        # Check for Retry-After header
                        retry_after = e.response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                delay = min(int(retry_after), self.MAX_RETRY_DELAY)
                            except ValueError:
                                pass

                        logger.warning(
                            f"{provider_name} rate limited (429). "
                            f"Retry {attempt + 1}/{self.MAX_RETRIES} in {delay}s"
                        )
                        time.sleep(delay)

                        # Exponential backoff for next attempt
                        delay = min(delay * 2, self.MAX_RETRY_DELAY)
                        continue
                    else:
                        logger.error(
                            f"{provider_name} rate limited (429). "
                            f"Max retries ({self.MAX_RETRIES}) exceeded"
                        )

                # For other errors, raise immediately
                raise

        # If we get here, we've exhausted retries
        raise last_exception

    def _parse_analysis_response(self, response: Dict) -> Dict[str, Any]:
        """
        Parse the AI response and extract structured analysis.

        Args:
            response: Raw API response

        Returns:
            Structured analysis result
        """
        import json
        import re

        try:
            # Extract the message content
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')

            # Try to extract JSON from the response
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'\{[^{}]*"relevance_score"[^{}]*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    # No JSON found, create a basic response
                    return {
                        'success': True,
                        'relevance_score': 0.5,
                        'summary': content[:500],
                        'flags': [],
                        'is_alert': False,
                        'raw_response': content,
                        'provider': self.provider,
                        'model': self._get_model_name()
                    }

            # Parse the JSON
            analysis = json.loads(json_str)

            return {
                'success': True,
                'relevance_score': float(analysis.get('relevance_score', 0)),
                'summary': analysis.get('summary', ''),
                'flags': analysis.get('flags', []),
                'is_alert': analysis.get('is_alert', False),
                'details': analysis.get('details', {}),
                'raw_response': content,
                'provider': self.provider,
                'model': self._get_model_name()
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from AI response: {e}")
            return {
                'success': True,
                'relevance_score': 0.5,
                'summary': f"Análisis completado (formato no estructurado): {content[:500]}",
                'flags': [],
                'is_alert': False,
                'raw_response': content,
                'provider': self.provider,
                'model': self._get_model_name()
            }

    def _get_model_name(self) -> str:
        """Get the model name for the current provider."""
        if self.provider == 'openai':
            return self.OPENAI_MODEL
        elif self.provider == 'deepseek':
            return self.DEEPSEEK_MODEL
        return 'unknown'

    def supports_vision(self) -> bool:
        """Check if the current provider supports image/vision analysis."""
        return self.provider in self.VISION_CAPABLE_PROVIDERS

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the AI API connection.

        Returns:
            dict with success status and details
        """
        try:
            # Simple test prompt
            test_prompt = "Responde solo con 'OK' si puedes leer este mensaje."

            if self.provider == 'openai':
                response = self._call_openai(test_prompt, [])
            elif self.provider == 'deepseek':
                response = self._call_deepseek(test_prompt, [])
            else:
                return {
                    'success': False,
                    'error': f'Proveedor no soportado: {self.provider}'
                }

            # Check response
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')

            return {
                'success': True,
                'provider': self.provider,
                'model': self._get_model_name(),
                'response': content[:100],
                'timestamp': datetime.utcnow().isoformat()
            }

        except httpx.HTTPStatusError as e:
            return {
                'success': False,
                'error': f'Error HTTP: {e.response.status_code}',
                'details': str(e)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def encode_image_file(file_path: str) -> str:
        """
        Encode an image file to base64.

        Args:
            file_path: Path to image file

        Returns:
            Base64 encoded string with data URI prefix
        """
        import mimetypes

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'image/jpeg'

        with open(file_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        return f'data:{mime_type};base64,{image_data}'
