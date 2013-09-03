# Copyright (c) 2012, 2013 Azavea, Inc.
# See LICENSE in the project root for copying permission

from portal.models import Location, LocationEdit
from django.contrib.gis import admin
from django import forms
from portal.widgets import MapWidget
from django.contrib.gis.geos import Point
import re
from django.conf import settings
from django.http import HttpResponseRedirect
from django.conf.urls.defaults import patterns, url
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.contrib.admin import SimpleListFilter
from django.utils.translation import ugettext_lazy as _

class PendingEditsFilter(SimpleListFilter):
    """
    Adds a pending edits filter for location view
    """
    title = 'Pending Edits'
    parameter_name = 'pending'

    def lookups(self, request, model_admin):
        return(
            ('True', _('Yes')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'True':
            return queryset.filter(locationedit__pending=True).distinct()


class LocationForm(forms.ModelForm):
    """Form subclass for location model form to use custom widget for google map
    and a custom clean method to properly handle points passed in as strings
    """

    geom = forms.CharField(label="Geocoded Point", widget=MapWidget())
    
    def __init__(self, *args, **kwargs):
        """
        Override __init__ method to add custom classes to fields based on whether
        or not the field has been edited and what type of edit was made.
        """
        super(LocationForm,self).__init__(*args, **kwargs)
        edits = self.instance.locationedit_set.filter(pending=True)
        bools = self.instance.get_boolean_fieldnames()

        # Loop through edits and apply classes to fields for highlighting
        for edit in edits.filter(edit_type='update'):
            if edit.fieldname in bools:
                edit.new_value = True if edit.new_value == 'True' else False
            self.initial[edit.fieldname] = edit.new_value
            field = self.fields[edit.fieldname]
            field.widget.attrs['class'] = edit.edit_type
        if edits.filter(edit_type='delete'):
            # If edit type is delete, all fields are red
            for field in self.fields.values():
                field.widget.attrs['class'] = 'delete'
        if edits.filter(edit_type='create'):
            # If edit type is create, all fields are green
            for field in self.fields.values():
                field.widget.attrs['class'] = 'create'

    def get_point(self, geom_string):
        """Takes a geom_string from cleaned_data and converts it to a point
        object. If unable to convert, raises a validation error.
        
        Arguments:
        - `geom_string`: string returned by the 'geom' input from the LocationForm
        Takes the form of 'POINT (<LNG> <LAT>)'
        """
        try:
            split_geom_string = re.findall(r'([-.\w]+)', geom_string)
            lng = float(split_geom_string[1])
            lat = float(split_geom_string[2])
            return Point(lng, lat)
        except (IndexError, ValueError):
            raise forms.ValidationError("Invalid point specified for location")
    
    def clean(self):
        """
        Need to create a Point object from string returned by form because
        of the way the map fills in the geocoded location form
        """
        self.cleaned_data = super(LocationForm, self).clean()

        try:
            self.cleaned_data['geom'] = self.get_point(self.cleaned_data['geom'])
            return self.cleaned_data
        except forms.ValidationError:
            # Need to pass a dummy point if invalid, or we get a 500 error
            # This point does not get saved, nothing happens to it
            self.cleaned_data['geom'] = Point(0, 0)
            raise forms.ValidationError("Invalid point specified for location")

    class Meta:
        model = Location
        
class LocationAdmin(admin.OSMGeoAdmin):

    # General Settings
    # Template override that adds buttons to propose/accept changes
    change_form_template = 'admin/portal/location/change_form.html'
    delete_confirmation_template = 'admin/portal/location/delete_confirmation.html'
    save_on_top = True
    save_on_bottom = False
    list_display = ['site_name', 'address', 'zip', 'phone', 'id', 'accepted']
    list_filter = ['is_hs', 'is_ehs', 'accept_ccap', 'is_cps_based', 'is_community_based',
                   'is_age_lt_3', 'is_age_gt_3', 'is_full_day', 'is_full_week', 'is_full_year',
                   'is_part_day', 'is_part_week', 'is_school_year', 'is_home_visiting']
    search_fields = ['site_name', 'address', 'zip', 'language_1', 'language_2', 'language_3']
    readonly_fields = ['neighborhood']
    form = LocationForm
    fieldsets = [
        (None,      {'fields': ['site_name', 'neighborhood']}),
        ('Address', {'fields': [('address', 'city'), ('state', 'zip'), 'geom']}),
        ('Contact', {'fields': ['phone', 'url']}),
        ('Hours/Duration', {'fields': [('is_full_day', 'is_part_day'),
                                       ('is_full_week', 'is_part_week'),
                                       ('is_school_year', 'is_full_year')]}),
        ('Flags',   {'fields': [('is_age_lt_3', 'is_age_gt_3'),
                                ('is_community_based', 'is_cps_based'),
                                ('is_hs', 'is_ehs'), 'accept_ccap']}),
        ('Other',   {'fields': [('ages', 'prg_hours', 'accred'),
                                ('language_1', 'language_2', 'language_3'),
                                'q_stmt']}),
    ]


admin.site.register(Location, LocationAdmin)

