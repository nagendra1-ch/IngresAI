import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="USER", nullable=False)  # "USER" or "ADMIN"
    created_at = Column(DateTime, default=func.now(), nullable=False)

    queries = relationship("QueryHistory", back_populates="user", cascade="all, delete-orphan")
    accesses = relationship("ResultAccess", back_populates="user", cascade="all, delete-orphan")

class Geography(Base):
    __tablename__ = "geographies"

    id = Column(Integer, primary_key=True, index=True)
    country_name = Column(String, default="India", nullable=False)
    state_name = Column(String, nullable=False)
    state_code = Column(String, nullable=True)
    district_name = Column(String, nullable=False)
    district_code = Column(String, nullable=True)
    mandal_name = Column(String, nullable=True)
    mandal_code = Column(String, nullable=True)
    village_name = Column(String, nullable=True)
    village_code = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Normalized fields for lookup (uppercase, whitespace-stripped)
    normalized_state_name = Column(String, index=True, nullable=False)
    normalized_district_name = Column(String, index=True, nullable=False)
    normalized_mandal_name = Column(String, index=True, nullable=True)
    normalized_village_name = Column(String, index=True, nullable=True)

    # Properties to match district level synonyms if needed
    @property
    def canonical_district_name(self):
        return self.district_name

    # Relationships
    aliases = relationship("GeographyAlias", back_populates="geography", cascade="all, delete-orphan")
    gwra_assessments = relationship("GWRAAssessment", back_populates="geography", cascade="all, delete-orphan")
    groundwater_observations = relationship("GroundwaterObservation", back_populates="geography", cascade="all, delete-orphan")
    rainfall_records = relationship("RainfallRecord", back_populates="geography", cascade="all, delete-orphan")
    queries = relationship("QueryHistory", back_populates="geography")
    accesses = relationship("ResultAccess", back_populates="geography", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("normalized_state_name", "normalized_district_name", "normalized_mandal_name", "normalized_village_name", name="uq_geography_path"),
    )

class GeographyAlias(Base):
    __tablename__ = "geography_aliases"

    id = Column(Integer, primary_key=True, index=True)
    geography_id = Column(Integer, ForeignKey("geographies.id"), nullable=False)
    alias_name = Column(String, nullable=False)
    alias_type = Column(String, nullable=False)  # "state", "district", "mandal", "village"
    normalized_alias_name = Column(String, index=True, nullable=False)

    geography = relationship("Geography", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("geography_id", "normalized_alias_name", name="uq_geo_alias"),
    )

class GWRAAssessment(Base):
    __tablename__ = "gwra_assessments"

    id = Column(Integer, primary_key=True, index=True)
    geography_id = Column(Integer, ForeignKey("geographies.id"), nullable=False, index=True)
    assessment_year = Column(Integer, index=True, nullable=False)
    data_version = Column(String, default="2025_v1", nullable=False)
    
    source_name = Column(String, nullable=False)
    source_document = Column(String, nullable=False)
    source_url = Column(String, nullable=True)

    annual_groundwater_recharge_ham = Column(Float, nullable=True)
    total_natural_discharges_ham = Column(Float, nullable=True)
    annual_extractable_groundwater_resource_ham = Column(Float, nullable=True)
    annual_groundwater_extraction_ham = Column(Float, nullable=True)
    annual_gw_allocation_domestic_ham = Column(Float, nullable=True)
    net_groundwater_availability_ham = Column(Float, nullable=True)
    stage_of_groundwater_extraction_percent = Column(Float, nullable=True)
    
    district_assessment_category = Column(String, nullable=True)
    mandal_assessment_categories = Column(Text, nullable=True)  # JSON summary string if available
    mandal_category_summary = Column(Text, nullable=True)  # JSON detail
    
    confidence_score = Column(Float, nullable=True)
    data_quality_status = Column(String, nullable=True)

    geography = relationship("Geography", back_populates="gwra_assessments")

    __table_args__ = (
        UniqueConstraint("geography_id", "assessment_year", "data_version", name="uq_gwra_geo_year_ver"),
    )

class GroundwaterObservation(Base):
    __tablename__ = "groundwater_observations"

    id = Column(Integer, primary_key=True, index=True)
    geography_id = Column(Integer, ForeignKey("geographies.id"), nullable=False, index=True)
    
    observation_date = Column(String, nullable=True)
    observation_year = Column(Integer, index=True, nullable=False)
    observation_month = Column(String, nullable=True)
    season = Column(String, nullable=True)
    
    monitoring_station = Column(String, nullable=False)
    depth_to_water_level_m_bgl = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    source = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    data_quality_status = Column(String, nullable=True)

    geography = relationship("Geography", back_populates="groundwater_observations")

    __table_args__ = (
        UniqueConstraint("geography_id", "observation_year", "monitoring_station", "observation_date", name="uq_observation_geo_year_station"),
    )

class RainfallRecord(Base):
    __tablename__ = "rainfall_records"

    id = Column(Integer, primary_key=True, index=True)
    geography_id = Column(Integer, ForeignKey("geographies.id"), nullable=False, index=True)
    
    rainfall_mm = Column(Float, nullable=False)
    rainfall_year = Column(Integer, index=True, nullable=False)
    rainfall_period = Column(String, nullable=False)  # "annual", "monsoon", "seasonal", "monthly"
    
    rainfall_source = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    data_quality_status = Column(String, nullable=True)

    geography = relationship("Geography", back_populates="rainfall_records")

    __table_args__ = (
        UniqueConstraint("geography_id", "rainfall_year", "rainfall_period", name="uq_rainfall_geo_year_period"),
    )

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    geography_id = Column(Integer, ForeignKey("geographies.id"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship("User", back_populates="queries")
    geography = relationship("Geography", back_populates="queries")

    @property
    def district_id(self):
        return self.geography_id

    @property
    def district(self):
        return self.geography

class ResultAccess(Base):
    __tablename__ = "result_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    geography_id = Column(Integer, ForeignKey("geographies.id"), nullable=False)
    access_type = Column(String, nullable=False)  # "search", "compare", "detail", "chat"
    accessed_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship("User", back_populates="accesses")
    geography = relationship("Geography", back_populates="accesses")

    @property
    def district_id(self):
        return self.geography_id

    @property
    def district(self):
        return self.geography

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    current_state_name = Column(String, nullable=True)
    current_district_name = Column(String, nullable=True)
    current_mandal_name = Column(String, nullable=True)
    current_village_name = Column(String, nullable=True)
    current_geography_id = Column(Integer, ForeignKey("geographies.id"), nullable=True)
    current_year = Column(Integer, nullable=True)
    current_period = Column(String, nullable=True)
    current_metric = Column(String, nullable=True)
    current_intent = Column(String, nullable=True)
    
    pending_intent = Column(String, nullable=True)
    pending_location = Column(String, nullable=True)
    last_user_question = Column(Text, nullable=True)
    last_assistant_answer = Column(Text, nullable=True)

    user = relationship("User", backref="conversations")
    geography = relationship("Geography", backref="conversations")

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False)
    sender = Column(String, nullable=False) # "user" or "assistant"
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    conversation = relationship("Conversation", backref="messages")
