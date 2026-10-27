from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Tuple
from app.models.document import Document, IngestionJob, Collection, Tag
from app.schemas.document import DocumentCreate, DocumentUpdate, CollectionCreate, TagCreate

def create_document_metadata(db: Session, obj_in: DocumentCreate, user_id: str) -> Document:
    db_obj = Document(**obj_in.model_dump(), status="pending", user_id=user_id)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_document(db: Session, doc_id: str, user_id: str) -> Optional[Document]:
    return db.query(Document).filter(Document.id == doc_id, Document.user_id == user_id).first()

def list_documents(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> Tuple[List[Document], int]:
    total = db.query(Document).filter(Document.user_id == user_id).count()
    items = db.query(Document).filter(Document.user_id == user_id).offset(skip).limit(limit).all()
    return items, total

def update_document(db: Session, db_obj: Document, obj_in: DocumentUpdate) -> Document:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def delete_document(db: Session, db_obj: Document) -> None:
    db.delete(db_obj)
    db.commit()

def create_ingestion_job(db: Session, document_id: str, job_type: str, user_id: str) -> IngestionJob:
    db_obj = IngestionJob(document_id=document_id, job_type=job_type, status="queued", user_id=user_id)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def list_ingestion_jobs_for_document(db: Session, document_id: str, user_id: str) -> List[IngestionJob]:
    return db.query(IngestionJob).filter(IngestionJob.document_id == document_id, IngestionJob.user_id == user_id).all()

def create_collection(db: Session, obj_in: CollectionCreate, user_id: str) -> Collection:
    db_obj = Collection(**obj_in.model_dump(), user_id=user_id)
    db.add(db_obj)
    try:
        db.commit()
        db.refresh(db_obj)
    except IntegrityError:
        db.rollback()
        raise ValueError("Collection with this name already exists for this user")
    return db_obj

def list_collections(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Collection]:
    return db.query(Collection).filter(Collection.user_id == user_id).offset(skip).limit(limit).all()

def get_collection(db: Session, collection_id: str, user_id: str) -> Optional[Collection]:
    return db.query(Collection).filter(Collection.id == collection_id, Collection.user_id == user_id).first()

def create_tag(db: Session, obj_in: TagCreate, user_id: str) -> Tag:
    db_obj = Tag(**obj_in.model_dump(), user_id=user_id)
    db.add(db_obj)
    try:
        db.commit()
        db.refresh(db_obj)
    except IntegrityError:
        db.rollback()
        raise ValueError("Tag with this name already exists for this user")
    return db_obj

def list_tags(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Tag]:
    return db.query(Tag).filter(Tag.user_id == user_id).offset(skip).limit(limit).all()

def get_tag(db: Session, tag_id: str, user_id: str) -> Optional[Tag]:
    return db.query(Tag).filter(Tag.id == tag_id, Tag.user_id == user_id).first()

def attach_document_to_collection(db: Session, document: Document, collection: Collection) -> Document:
    if collection not in document.collections:
        document.collections.append(collection)
        db.commit()
        db.refresh(document)
    return document

def attach_tag_to_document(db: Session, document: Document, tag: Tag) -> Document:
    if tag not in document.tags:
        document.tags.append(tag)
        db.commit()
        db.refresh(document)
    return document

def detach_tag_from_document(db: Session, document: Document, tag: Tag) -> Document:
    if tag in document.tags:
        document.tags.remove(tag)
        db.commit()
        db.refresh(document)
    return document
