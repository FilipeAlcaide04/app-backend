"""
Processador de documentos PDF
"""
import PyPDF2
import pdfplumber
from typing import Optional
import os

class DocumentProcessor:
    """Processa documentos PDF e extrai texto"""

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> Optional[str]:
        """
        Extrai texto de um ficheiro PDF

        Args:
            file_path: Caminho para o ficheiro PDF

        Returns:
            Texto extraído ou None em caso de erro
        """
        try:
            text_parts = []

            # Tenta com pdfplumber primeiro (melhor qualidade)
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
            except Exception as e:
                print(f"Erro ao usar pdfplumber: {e}")
                # Fallback para PyPDF2
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)

            return "\n\n".join(text_parts) if text_parts else None
        except Exception as e:
            print(f"Erro ao extrair texto do PDF: {e}")
            return None

    @staticmethod
    def get_file_size(file_path: str) -> int:
        """Retorna o tamanho do ficheiro em bytes"""
        try:
            return os.path.getsize(file_path)
        except:
            return 0
