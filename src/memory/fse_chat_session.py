from typing import Optional, Dict, List, Any

from core_rag.memory.chat_session import ChatSession
from core_rag.memory import session_store
from core_rag.memory.db import init_db as init_core_rag_db

from memory.fse_profile import (
    get_student_profile,
    upsert_student_profile,
    init_fse_schema,
    add_citation,
    get_citations,
    get_last_assistant_message_index,
)


class FSEChatSession(ChatSession):

    def __init__(self, user_id: str, session_id: str = None, config: dict = None):
        super().__init__(user_id=user_id, session_id=session_id, config=config)
        init_fse_schema(config)

    @property
    def rag(self):
        if self._rag is None:
            from retrieval.fse_unified_rag import FSEUnifiedRAG
            self._rag = FSEUnifiedRAG()
        return self._rag

    @rag.setter
    def rag(self, value):
        self._rag = value

    def chat(self, query: str, stream: bool = False, **kwargs) -> Any:
        if not kwargs.get('return_debug_info', False):
            return super().chat(query, stream, **kwargs)

        current_index = session_store.add_message(
            session_id=self.session_id,
            user_id=self.user_id,
            role='user',
            content=query,
            config=self.config,
        )
        session_store.touch_session(self.session_id, self.config)

        active_user_count = session_store.count_active_user_messages(self.session_id, self.config)
        if active_user_count >= self.compression_trigger:
            self._compress_and_archive(exclude_index=current_index)

        history = self._build_history(current_user_index=current_index)

        raw_result = self.rag.answer_question(
            query=query,
            conversation_history=history if history else None,
            stream=False,
            **kwargs,
        )

        if isinstance(raw_result, tuple):
            answer, sources, debug = raw_result
        else:
            answer, sources, debug = raw_result, [], {}

        assistant_index = session_store.add_message(
            session_id=self.session_id,
            user_id=self.user_id,
            role='assistant',
            content=answer,
            config=self.config,
        )
        self._store_citations(assistant_index, sources)

        return answer, sources, debug

    def get_profile(self) -> Optional[Dict]:
        return get_student_profile(self.user_id, self.config)

    def update_profile(
        self,
        major: str = None,
        catalog_year: int = None,
        minor: str = None,
        additional_program_asked: bool = None,
    ) -> bool:
        return upsert_student_profile(
            user_id=self.user_id,
            major=major,
            catalog_year=catalog_year,
            minor=minor,
            additional_program_asked=additional_program_asked,
            config=self.config,
        )

    def chat_with_context(self, query: str, stream: bool = False, **kwargs):
        profile = self.get_profile()
        if profile:
            kwargs.setdefault('student_program', profile.get('major'))
            kwargs.setdefault('student_year', profile.get('catalog_year'))
            kwargs.setdefault('student_minor', profile.get('minor'))
        return self.chat(query=query, stream=stream, **kwargs)

    def _store_citations(self, message_index: int, sources: List[Dict]):
        for source in sources:
            try:
                add_citation(
                    session_id=self.session_id,
                    message_index=message_index,
                    collection=source.get('collection', ''),
                    metadata=source.get('metadata', {}),
                    config=self.config,
                )
            except Exception:
                pass

    def get_last_citations(self) -> List[Dict]:
        msg_index = get_last_assistant_message_index(self.session_id, self.config)
        if msg_index is None:
            return []
        return get_citations(self.session_id, msg_index, self.config)


def init_all_schemas(config: dict = None):
    init_core_rag_db(config)
    init_fse_schema(config)
