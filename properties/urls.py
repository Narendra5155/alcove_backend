from django.urls import path

from . import api, views

api_urlpatterns = [
    path("properties/search/", api.PropertySearchView.as_view()),
    path("properties/amenities/", api.AmenityListView.as_view()),
    path("properties/<slug:slug>/", api.PropertyDetailView.as_view()),
    path("properties/<slug:slug>/availability/", api.AvailabilityView.as_view()),
    path("owner/properties/", api.OwnerPropertyListCreate.as_view()),
    path("owner/properties/<int:pk>/", api.OwnerPropertyDetail.as_view()),
    path("owner/properties/<int:pk>/images/", api.OwnerPropertyImages.as_view()),
    path("owner/properties/<int:pk>/images/<int:image_id>/", api.OwnerPropertyImageDetail.as_view()),
    path("owner/properties/<int:pk>/rooms/", api.OwnerRoomListCreate.as_view()),
    path("owner/properties/<int:pk>/rooms/<int:room_id>/", api.OwnerRoomDetail.as_view()),
]

urlpatterns = [
    path("stays/", views.search_page, name="search"),
    path("stays/<slug:slug>/", views.property_page, name="property_detail"),
    path("dashboard/owner/properties/", views.owner_property_list, name="owner_properties"),
    path("dashboard/owner/properties/new/", views.owner_property_form, name="owner_property_new"),
    path("dashboard/owner/properties/<int:pk>/edit/", views.owner_property_form, name="owner_property_edit"),
]
