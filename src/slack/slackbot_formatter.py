import re
from typing import List


class SlackFormatter:
    
    def convert_markdown_to_slack(self, text: str) -> str:
        text = self._convert_tables_to_slack(text)
        text = self._improve_numbered_lists(text)
        text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
        text = re.sub(r'^(\s*)[*\-]\s+', r'\1• ', text, flags=re.MULTILINE)
        text = re.sub(r'^(\s*)(\d+)\.\s+', r'\1\2. ', text, flags=re.MULTILINE)
        text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'_\1_', text)
        text = re.sub(r'^#+\s*(.*?)$', r'*\1*', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)
        text = re.sub(r'SLACKBOLD_(.*?)_SLACKBOLD', r'*\1*', text)
        return text
    
    def _convert_tables_to_slack(self, text: str) -> str:
        table_pattern = r'^(\|.*?\|)$'
        lines = text.split('\n')
        result_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if re.match(table_pattern, line):
                table_lines = []
                while i < len(lines) and re.match(table_pattern, lines[i].strip()):
                    table_lines.append(lines[i].strip())
                    i += 1
                
                if len(table_lines) >= 2:
                    converted_table = self._format_table_as_numbered_list(table_lines)
                    result_lines.extend(converted_table)
                else:
                    result_lines.extend(table_lines)
                
                i -= 1
            else:
                result_lines.append(lines[i])
            
            i += 1
        
        return '\n'.join(result_lines)
    
    def _format_table_as_numbered_list(self, table_lines: List[str]) -> List[str]:
        if len(table_lines) < 3:
            return table_lines
        
        header_row = table_lines[0]
        headers = [col.strip() for col in header_row.split('|')[1:-1]]
        data_rows = table_lines[2:]
        result = []
        
        for idx, row in enumerate(data_rows, 1):
            cols = [col.strip() for col in row.split('|')[1:-1]]
            
            for header, value in zip(headers, cols):
                if value.strip():
                    clean_value = value.replace('<br>', '\n   ').replace('• ', '').strip()
                    result.append(f"   • SLACKBOLD_{header}_SLACKBOLD: {clean_value}")
            
            result.append("")
        
        return result
    
    def _improve_numbered_lists(self, text: str) -> str:
        lines = text.split('\n')
        result_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if re.match(r'^\d+\.\s+', line.strip()):
                section_lines = []
                current_section_start = i
                
                while i < len(lines):
                    current_line = lines[i].strip()
                    
                    if re.match(r'^\d+\.\s+', current_line):
                        section_lines.append(lines[i])
                    elif current_line == '---' or current_line == '' or i == len(lines) - 1:
                        if current_line != '---' and current_line != '' and i == len(lines) - 1:
                            section_lines.append(lines[i])
                        break
                    else:
                        section_lines.append(lines[i])
                    
                    i += 1
                
                if len(section_lines) > 0:
                    improved_section = self._convert_section_to_bullets(section_lines)
                    result_lines.extend(improved_section)
                    
                    if i < len(lines) and lines[i].strip() == '---':
                        result_lines.append(lines[i])
            else:
                result_lines.append(lines[i])
            
            i += 1
        
        return '\n'.join(result_lines)
    
    def _convert_section_to_bullets(self, section_lines: List[str]) -> List[str]:
        result = []
        current_group = []
        
        for line in section_lines:
            stripped = line.strip()
            
            if re.match(r'^\d+\.\s+', stripped):
                if current_group:
                    result.extend(self._format_group_as_bullets(current_group))
                    current_group = []
                
                content = re.sub(r'^\d+\.\s+', '', stripped)
                if self._looks_like_section_header(content):
                    result.append(f"*{content}*")
                else:
                    current_group = [f"• {content}"]
            else:
                if current_group:
                    current_group.append(line)
                else:
                    result.append(line)
        
        if current_group:
            result.extend(self._format_group_as_bullets(current_group))
        
        return result
    
    def _looks_like_section_header(self, text: str) -> bool:
        header_indicators = [
            'perspectives', 'areas', 'systems', 'engineering', 'development',
            'specialized', 'emerging', 'infrastructure', 'cross-disciplinary',
            'requirements', 'electives', 'courses', 'track', 'category'
        ]
        text_lower = text.lower()
        
        if len(text.split()) <= 6 and any(indicator in text_lower for indicator in header_indicators):
            return True
        
        if text.endswith(':') or text.endswith(' –'):
            return True
            
        return False
    
    def _format_group_as_bullets(self, group_lines: List[str]) -> List[str]:
        return group_lines + ['']
    
    def format_response(self, response: str, sources: list) -> str:
        slack_formatted_response = self.convert_markdown_to_slack(response)
        formatted = f"*PantherBot Academic Assistant*\n\n{slack_formatted_response}"
        
        if sources:
            formatted += "\n\nSources:\n"
            for i, source in enumerate(sources[:3], 1):
                try:
                    if isinstance(source, dict):
                        metadata = source.get('metadata', {})
                        program = metadata.get('program_full', 'N/A') 
                        year = metadata.get('year', 'N/A')
                        section = metadata.get('section_name', 'N/A')
                        formatted += f"{i}. {program} ({year}) - {section}\n"
                    else:
                        formatted += f"{i}. Academic Resource\n"
                except Exception:
                    formatted += f"{i}. Academic Resource\n"
        
        return formatted